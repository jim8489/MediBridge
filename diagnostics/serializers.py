from rest_framework import serializers

from accounts.models import DoctorProfile, PatientProfile, User
from organizations.models import CenterMembership, DiagnosticCenter
from patients.models import DoctorPatientRelationship
from .models import DiagnosticReport, DiagnosticRequest, DiagnosticService
import os

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import AIAnalysis

from accounts.models import DoctorProfile, PatientProfile, User
from organizations.models import CenterMembership, DiagnosticCenter
from patients.models import DoctorPatientRelationship
from .models import (
    DiagnosticAttachment,
    DiagnosticReport,
    DiagnosticRequest,
    DiagnosticService,
    validate_diagnostic_file,
)


class DiagnosticServiceSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source="center.name", read_only=True)

    class Meta:
        model = DiagnosticService
        fields = ("id", "center", "center_name", "service_code", "name", "category", "description", "requires_referral", "fee", "is_active", "created_at")
        read_only_fields = ("id", "center_name", "created_at")

    def validate_center(self, center):
        user = self.context["request"].user
        membership = CenterMembership.objects.filter(
            user=user, center=center, status=CenterMembership.Status.ACTIVE,
            staff_role__in=(CenterMembership.StaffRole.OWNER, CenterMembership.StaffRole.CENTER_ADMIN),
            center__verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
        ).exists()
        if not membership:
            raise serializers.ValidationError("You must be an active center owner or administrator for this center.")
        return center


class DiagnosticRequestSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=PatientProfile.objects.all(), required=False)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    center_name = serializers.CharField(source="service.center.name", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    ordering_doctor_name = serializers.CharField(source="ordering_doctor.user.get_full_name", read_only=True, default="")

    class Meta:
        model = DiagnosticRequest
        fields = (
            "id", "patient", "patient_number", "service", "service_name", "center_name",
            "requested_by", "requested_by_email", "ordering_doctor", "ordering_doctor_name",
            "clinical_indication", "status", "scheduled_at", "accepted_at", "started_at",
            "completed_at", "created_at",
        )
        read_only_fields = ("id", "requested_by", "ordering_doctor", "status", "accepted_at", "started_at", "completed_at", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        service = attrs["service"]
        if not service.is_active or not service.center.is_active or service.center.verification_status != DiagnosticCenter.VerificationStatus.APPROVED:
            raise serializers.ValidationError({"service": "This diagnostic service is not currently available."})
        if request.user.role == User.Role.PATIENT:
            patient = request.user.patient_profile
            if "patient" in attrs and attrs["patient"] != patient:
                raise serializers.ValidationError({"patient": "You can only request a test for yourself."})
            if service.requires_referral:
                raise serializers.ValidationError({"service": "This service requires a doctor's referral."})
            attrs["patient"] = patient
        elif request.user.role == User.Role.DOCTOR:
            doctor = getattr(request.user, "doctor_profile", None)
            if not doctor or doctor.verification_status != DoctorProfile.VerificationStatus.APPROVED:
                raise serializers.ValidationError("An approved doctor profile is required.")
            patient = attrs.get("patient")
            if not patient:
                raise serializers.ValidationError({"patient": "A patient is required for a doctor-initiated request."})
            if not DoctorPatientRelationship.objects.filter(
                patient=patient, doctor=doctor, status=DoctorPatientRelationship.Status.ACTIVE
            ).exists():
                raise serializers.ValidationError({"patient": "You do not have an active care relationship with this patient."})
        else:
            raise serializers.ValidationError("Only patients and approved doctors can create diagnostic requests.")
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["requested_by"] = user
        if user.role == User.Role.DOCTOR:
            validated_data["ordering_doctor"] = user.doctor_profile
        return super().create(validated_data)


class DiagnosticReportCreateSerializer(serializers.ModelSerializer):

    ai_analysis_id = serializers.UUIDField(
        required=False,
        write_only=True,
    )

    class Meta:
        model = DiagnosticReport
        fields = (
            "findings",
            "impression",
            "ai_analysis_id",
        )

    def validate_findings(self, value):

        if not isinstance(value, dict) or not value:
            raise serializers.ValidationError(
                "findings must be a non-empty JSON object."
            )

        if "ai_assistance" in value:
            raise serializers.ValidationError(
                "'ai_assistance' is reserved for the system."
            )

        return value

class DiagnosticReportReadSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="request.patient.patient_number", read_only=True)
    service_name = serializers.CharField(source="request.service.name", read_only=True)
    center_name = serializers.CharField(source="request.service.center.name", read_only=True)
    prepared_by_email = serializers.EmailField(source="prepared_by.email", read_only=True)
    verified_by_email = serializers.EmailField(source="verified_by.email", read_only=True, default=None)

    class Meta:
        model = DiagnosticReport
        fields = (
            "id", "request", "patient_number", "service_name", "center_name", "findings",
            "impression", "prepared_by", "prepared_by_email", "verified_by", "verified_by_email",
            "status", "submitted_at", "verified_at", "released_at",
        )
class DiagnosticAttachmentSerializer(serializers.ModelSerializer):
    """
    Handles secure diagnostic image and document uploads.

    The diagnostic request and uploader are assigned by the backend,
    never trusted from the client's submitted JSON.
    """

    file = serializers.FileField(write_only=True)

    request = serializers.PrimaryKeyRelatedField(read_only=True)
    uploaded_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DiagnosticAttachment
        fields = (
            "id",
            "request",
            "file",
            "original_filename",
            "content_type",
            "size_bytes",
            "attachment_type",
            "uploaded_by",
            "created_at",
        )

        read_only_fields = (
            "id",
            "request",
            "original_filename",
            "content_type",
            "size_bytes",
            "uploaded_by",
            "created_at",
        )

    def validate_file(self, uploaded_file):
        """
        Validate file size, extension and file signature.
        """

        try:
            validate_diagnostic_file(uploaded_file)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

        return uploaded_file

    def validate(self, attrs):
        """
        Validate uploader permissions and attachment type.
        """

        request = self.context["request"]
        diagnostic_request = self.context.get("diagnostic_request")

        if diagnostic_request is None:
            raise serializers.ValidationError(
                "Diagnostic request context is missing."
            )

        user = request.user

        if user.role != User.Role.DIAGNOSTIC_STAFF:
            raise serializers.ValidationError(
                "Only diagnostic-center staff can upload diagnostic attachments."
            )

        # Confirm that the user belongs to the assigned center.
        membership_exists = CenterMembership.objects.filter(
            user=user,
            center=diagnostic_request.service.center,
            status=CenterMembership.Status.ACTIVE,
            center__is_active=True,
            center__verification_status=(
                DiagnosticCenter.VerificationStatus.APPROVED
            ),
        ).exists()

        if not membership_exists:
            raise serializers.ValidationError(
                "You are not authorized to upload files for this diagnostic request."
            )

        # Files can only be added while the investigation is in progress.
        if diagnostic_request.status != DiagnosticRequest.Status.IN_PROGRESS:
            raise serializers.ValidationError(
                "Attachments can only be uploaded for investigations in progress."
            )

        uploaded_file = attrs["file"]
        extension = os.path.splitext(uploaded_file.name)[1].lower()

        attachment_type = attrs["attachment_type"]

        if (
            attachment_type == DiagnosticAttachment.AttachmentType.CLINICAL_IMAGE
            and extension not in (".jpg", ".jpeg", ".png")
        ):
            raise serializers.ValidationError({
                "file": "Clinical images must be JPEG or PNG."
            })

        if (
            attachment_type == DiagnosticAttachment.AttachmentType.REPORT_DOCUMENT
            and extension != ".pdf"
        ):
            raise serializers.ValidationError({
                "file": "Report documents must be PDF files."
            })

        return attrs

    def create(self, validated_data):
        """
        Assign ownership and file metadata on the server.
        """

        uploaded_file = validated_data["file"]

        extension = os.path.splitext(uploaded_file.name)[1].lower()

        detected_content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".pdf": "application/pdf",
        }

        validated_data["request"] = self.context["diagnostic_request"]

        validated_data["uploaded_by"] = self.context["request"].user

        validated_data["original_filename"] = os.path.basename(
            uploaded_file.name
        )[:255]

        validated_data["content_type"] = detected_content_types[extension]

        validated_data["size_bytes"] = uploaded_file.size

        return super().create(validated_data)

class AIAnalysisRequestSerializer(serializers.Serializer):

    attachment_id = serializers.UUIDField(
        required=True
    )


class AIAnalysisReviewSerializer(serializers.Serializer):

    review_status = serializers.ChoiceField(
        choices=[
            (
                AIAnalysis.ReviewStatus.ACCEPTED,
                "Accepted",
            ),
            (
                AIAnalysis.ReviewStatus.REJECTED,
                "Rejected",
            ),
        ]
    )

    review_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )

    def validate(self, attrs):

        if (
            attrs["review_status"]
            == AIAnalysis.ReviewStatus.REJECTED
            and not attrs.get("review_notes", "").strip()
        ):
            raise serializers.ValidationError({
                "review_notes": (
                    "Please provide a reason for rejecting "
                    "the AI analysis."
                )
            })

        return attrs


class AIAnalysisReadSerializer(serializers.ModelSerializer):

    model_key = serializers.CharField(
        source="model.model_key",
        read_only=True,
    )

    model_name = serializers.CharField(
        source="model.name",
        read_only=True,
    )

    model_version = serializers.CharField(
        source="model.version",
        read_only=True,
    )

    class Meta:
        model = AIAnalysis

        fields = [
            "id",
            "diagnostic_request",
            "attachment",
            "model",
            "model_key",
            "model_name",
            "model_version",
            "status",
            "pathology_scores",
            "score_semantics",
            "model_output",
            "error_message",
            "review_status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "started_at",
            "completed_at",
        ]

        read_only_fields = fields