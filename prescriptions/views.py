from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from .models import Prescription
from .serializers import PrescriptionSerializer

from django.http import FileResponse
from config.renderers import PDFRenderer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from .pdf import generate_prescription_pdf


class PrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Prescription.objects.select_related("patient__user", "doctor__user", "consultation").prefetch_related("items")
        if user.role == User.Role.PATIENT:
            return qs.filter(patient__user=user, status=Prescription.Status.ISSUED)
        if user.role == User.Role.DOCTOR:
            return qs.filter(doctor__user=user)
        if user.is_staff:
            return qs
        return qs.none()

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.DOCTOR:
            raise PermissionDenied("Only doctors can create prescriptions.")
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        request=None,
        responses={200: PrescriptionSerializer},
        summary="Issue a draft prescription",
        tags=["Prescriptions"],
    )
    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        prescription = self.get_object()
        if request.user.role != User.Role.DOCTOR or prescription.doctor.user_id != request.user.id:
            raise PermissionDenied("Only the issuing doctor can issue this prescription.")
        if prescription.status != Prescription.Status.DRAFT:
            raise ValidationError("Only draft prescriptions can be issued.")
        prescription.status = Prescription.Status.ISSUED
        prescription.issued_at = timezone.now()
        prescription.save(update_fields=["status", "issued_at", "updated_at"])
        return Response(self.get_serializer(prescription).data)
    
    @extend_schema(
        operation_id="download_prescription_pdf",
        summary="Download an issued prescription as PDF",
        description=(
            "Downloads a formatted prescription containing "
            "patient details, doctor details and medication instructions."
        ),
        responses={
            (200, "application/pdf"): OpenApiTypes.BINARY,
        },
        tags=["Prescriptions"],
    )
    @action(
       detail=True,
       methods=["get"],
       url_path="download",
       renderer_classes=[PDFRenderer],
    )
    def download_pdf(self, request, *args, **kwargs):

        prescription = self.get_object()

        if prescription.status != Prescription.Status.ISSUED:
            raise PermissionDenied(
                "Only issued prescriptions can be downloaded."
            )

        pdf_file = generate_prescription_pdf(prescription)

        filename = (
            f"{prescription.prescription_number}.pdf"
        )

        return FileResponse(
            pdf_file,
            as_attachment=True,
            filename=filename,
            content_type="application/pdf",
        )