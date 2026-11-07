from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import DoctorProfile, User
from .models import Consultation, DoctorPatientRelationship, Observation
from .serializers import (
    ConsultationSerializer,
    DoctorPatientRelationshipSerializer,
    ObservationSerializer,
    RelationshipCreateSerializer,
)


class DoctorPatientRelationshipListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.PATIENT:
            return DoctorPatientRelationship.objects.filter(patient=user.patient_profile).select_related("doctor__user", "patient")
        if user.role == User.Role.DOCTOR:
            return DoctorPatientRelationship.objects.filter(doctor__user=user).select_related("doctor__user", "patient__user")
        return DoctorPatientRelationship.objects.none()

    def get_serializer_class(self):
        return RelationshipCreateSerializer if self.request.method == "POST" else DoctorPatientRelationshipSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.PATIENT:
            raise PermissionDenied("Only patients can initiate a doctor connection in this version.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            relationship = serializer.save()
        except Exception as exc:
            # Convert the conditional unique constraint conflict into an API validation response.
            from django.db import IntegrityError
            if isinstance(exc, IntegrityError):
                raise ValidationError({"doctor": "A pending or active relationship already exists."})
            raise
        output = DoctorPatientRelationshipSerializer(relationship, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class RelationshipActionView(viewsets.ViewSet):
    serializer_class = DoctorPatientRelationshipSerializer
    permission_classes = [IsAuthenticated]
    def _get_relationship(self, pk):
        try:
            return DoctorPatientRelationship.objects.select_related("patient", "doctor__user").get(pk=pk)
        except DoctorPatientRelationship.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Relationship not found.")

    @extend_schema(
        request=None,
        responses={200: DoctorPatientRelationshipSerializer},
        summary="Accept a doctor-patient relationship",
        tags=["Medical Records"],
    )
    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        relationship = self._get_relationship(pk)

        if (
            request.user.role != User.Role.DOCTOR
            or relationship.doctor.user_id != request.user.id
        ):
            raise PermissionDenied(
                "Only the requested doctor can accept this relationship."
            )

        if (
            relationship.doctor.verification_status
            != DoctorProfile.VerificationStatus.APPROVED
        ):
            raise PermissionDenied(
                "An approved doctor profile is required."
            )

        if relationship.status != DoctorPatientRelationship.Status.PENDING:
            raise ValidationError(
                "Only pending relationships can be accepted."
            )

        relationship.status = DoctorPatientRelationship.Status.ACTIVE
        relationship.started_at = timezone.now()

        relationship.save(
            update_fields=["status", "started_at", "updated_at"]
        )

        return Response(
            DoctorPatientRelationshipSerializer(relationship).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={200: DoctorPatientRelationshipSerializer},
        summary="Revoke a doctor-patient relationship",
        tags=["Medical Records"],
    )
    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        relationship = self._get_relationship(pk)

        allowed = (
            request.user.role == User.Role.PATIENT
            and relationship.patient.user_id == request.user.id
        ) or (
            request.user.role == User.Role.DOCTOR
            and relationship.doctor.user_id == request.user.id
        )

        if not allowed:
            raise PermissionDenied(
                "Only the patient or connected doctor can revoke this relationship."
            )

        if relationship.status != DoctorPatientRelationship.Status.ACTIVE:
            raise ValidationError(
                "Only active relationships can be revoked."
            )

        relationship.status = DoctorPatientRelationship.Status.REVOKED
        relationship.ended_at = timezone.now()

        relationship.save(
            update_fields=["status", "ended_at", "updated_at"]
        )

        return Response(
            DoctorPatientRelationshipSerializer(relationship).data,
            status=status.HTTP_200_OK,
        )

class ConsultationViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.PATIENT:
            return Consultation.objects.filter(
                patient__user=user, status__in=(Consultation.Status.SIGNED, Consultation.Status.AMENDED)
            ).select_related("patient__user", "doctor__user")
        if user.role == User.Role.DOCTOR:
            return Consultation.objects.filter(doctor__user=user).select_related("patient__user", "doctor__user")
        return Consultation.objects.none()

    @extend_schema(summary="Create a consultation (approved doctor only)", tags=["Medical Records"])
    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.DOCTOR:
            raise PermissionDenied("Only doctors can create consultations.")
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="sign")
    def sign(self, request, pk=None):
        consultation = self.get_object()
        if request.user.role != User.Role.DOCTOR or consultation.doctor.user_id != request.user.id:
            raise PermissionDenied("Only the authoring doctor can sign this consultation.")
        if consultation.status != Consultation.Status.DRAFT:
            raise ValidationError("Only draft consultations can be signed.")
        consultation.status = Consultation.Status.SIGNED
        consultation.signed_at = timezone.now()
        consultation.save(update_fields=["status", "signed_at", "updated_at"])
        return Response(self.get_serializer(consultation).data)


class ObservationViewSet(viewsets.ModelViewSet):
    serializer_class = ObservationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.PATIENT:
            return Observation.objects.filter(patient__user=user).select_related("patient__user", "recorded_by", "consultation")
        if user.role == User.Role.DOCTOR:
            return Observation.objects.filter(
                patient__doctor_relationships__doctor__user=user,
                patient__doctor_relationships__status=DoctorPatientRelationship.Status.ACTIVE,
            ).select_related("patient__user", "recorded_by", "consultation").distinct()
        return Observation.objects.none()

    def create(self, request, *args, **kwargs):
        if request.user.role not in (User.Role.PATIENT, User.Role.DOCTOR):
            raise PermissionDenied("Only patients and doctors can create observations.")
        return super().create(request, *args, **kwargs)
