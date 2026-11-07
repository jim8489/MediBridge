import uuid

from django.conf import settings
from django.db import models

from accounts.models import PatientProfile, DoctorProfile
from organizations.models import DiagnosticCenter
import os

from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

MAX_DIAGNOSTIC_FILE_SIZE = 15 * 1024 * 1024

PRIVATE_DIAGNOSTIC_STORAGE = FileSystemStorage(
    location=settings.BASE_DIR / "private_media",
    base_url="/private-media-not-public/"
)


def validate_diagnostic_file(uploaded_file):
    """
    Validate the size, extension and actual file signature.
    """

    if uploaded_file.size > MAX_DIAGNOSTIC_FILE_SIZE:
        raise ValidationError(
            "File size cannot exceed 15 MB."
        )

    extension = os.path.splitext(uploaded_file.name)[1].lower()

    uploaded_file.seek(0)
    file_signature = uploaded_file.read(8)
    uploaded_file.seek(0)

    valid_signatures = {
        ".jpg": file_signature.startswith(b"\xff\xd8\xff"),
        ".jpeg": file_signature.startswith(b"\xff\xd8\xff"),
        ".png": file_signature.startswith(b"\x89PNG\r\n\x1a\n"),
        ".pdf": file_signature.startswith(b"%PDF-"),
    }

    if extension not in valid_signatures:
        raise ValidationError(
            "Only JPEG, PNG and PDF files are supported."
        )

    if not valid_signatures[extension]:
        raise ValidationError(
            "The uploaded file does not match its extension."
        )


def diagnostic_attachment_path(instance, filename):
    """
    Generate a unique storage path instead of trusting
    the original uploaded filename.
    """

    extension = os.path.splitext(filename)[1].lower()

    return (
        f"diagnostic_attachments/"
        f"{instance.request_id}/"
        f"{uuid.uuid4().hex}{extension}"
    )
    

class DiagnosticService(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    center = models.ForeignKey(DiagnosticCenter, on_delete=models.PROTECT, related_name="services")
    service_code = models.CharField(max_length=40)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    requires_referral = models.BooleanField(default=False)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("center", "service_code"), name="unique_center_service_code")]
        indexes = [models.Index(fields=("center", "is_active")), models.Index(fields=("category", "is_active"))]

    def __str__(self):
        return f"{self.name} — {self.center.name}"


class DiagnosticRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        ACCEPTED = "ACCEPTED", "Accepted"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        REPORT_PENDING = "REPORT_PENDING", "Report pending verification"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="diagnostic_requests")
    service = models.ForeignKey(DiagnosticService, on_delete=models.PROTECT, related_name="requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_diagnostic_requests")
    ordering_doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, null=True, blank=True, related_name="diagnostic_requests")
    clinical_indication = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("patient", "status")),
            models.Index(fields=("service", "status")),
            models.Index(fields=("ordering_doctor", "created_at")),
        ]

    def __str__(self):
        return f"{self.service.name} — {self.patient.patient_number} ({self.status})"


class DiagnosticReport(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted for verification"
        VERIFIED = "VERIFIED", "Verified"
        RELEASED = "RELEASED", "Released"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(DiagnosticRequest, on_delete=models.PROTECT, related_name="report")
    findings = models.JSONField(default=dict, help_text="Structured result values; do not include untrusted executable content.")
    impression = models.TextField()
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_diagnostic_reports")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="verified_diagnostic_reports")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        return f"Report for {self.request} ({self.status})"

class DiagnosticAttachment(models.Model):

    class AttachmentType(models.TextChoices):
        CLINICAL_IMAGE = "CLINICAL_IMAGE", "Clinical Image"
        REPORT_DOCUMENT = "REPORT_DOCUMENT", "Report Document"
        SUPPORTING_DOCUMENT = "SUPPORTING_DOCUMENT", "Supporting Document"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    request = models.ForeignKey(
        DiagnosticRequest,
        on_delete=models.PROTECT,
        related_name="attachments"
    )

    file = models.FileField(
        storage=PRIVATE_DIAGNOSTIC_STORAGE,
        upload_to=diagnostic_attachment_path,
        validators=[validate_diagnostic_file],
        max_length=255
    )

    original_filename = models.CharField(
        max_length=255
    )

    content_type = models.CharField(
        max_length=100
    )

    size_bytes = models.PositiveBigIntegerField()

    attachment_type = models.CharField(
        max_length=25,
        choices=AttachmentType.choices
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="diagnostic_attachments"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ("-created_at",)

        indexes = [
            models.Index(
                fields=("request", "created_at")
            )
        ]

    def __str__(self):
        return (
            f"{self.original_filename} "
            f"— {self.request_id}"
        )
        
class AIModel(models.Model):

    class TaskType(models.TextChoices):
        CHEST_XRAY_CLASSIFICATION = (
            "CHEST_XRAY_CLASSIFICATION",
            "Chest X-ray Classification",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    model_key = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    version = models.CharField(max_length=50)

    task_type = models.CharField(
        max_length=50,
        choices=TaskType.choices,
    )

    framework = models.CharField(max_length=50)
    architecture = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    input_specification = models.JSONField(
        default=dict,
        blank=True,
    )

    class_labels = models.JSONField(
        default=list,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("model_key", "-created_at")

        constraints = [
            models.UniqueConstraint(
                fields=("model_key", "version"),
                name="unique_ai_model_version",
            )
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"
    
    
class AIAnalysis(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    diagnostic_request = models.ForeignKey(
        DiagnosticRequest,
        on_delete=models.PROTECT,
        related_name="ai_analyses",
    )

    attachment = models.ForeignKey(
        DiagnosticAttachment,
        on_delete=models.PROTECT,
        related_name="ai_analyses",
    )

    model = models.ForeignKey(
        AIModel,
        on_delete=models.PROTECT,
        related_name="analyses",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_ai_analyses",
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
    )
    pathology_scores = models.JSONField(
    default=dict,
    blank=True,
    )

    score_semantics = models.TextField(
    blank=True,
    )
    
    model_output = models.JSONField(
        default=dict,
        blank=True,
    )

    error_message = models.TextField(blank=True)

    review_status = models.CharField(
        max_length=15,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_ai_analyses",
    )

    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

        indexes = [
            models.Index(
                fields=("diagnostic_request", "status"),
            ),
            models.Index(
                fields=("model", "created_at"),
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.attachment_id
            and self.diagnostic_request_id
        ):
            if self.attachment.request_id != self.diagnostic_request_id:
                raise ValidationError(
                    "Attachment must belong to the selected diagnostic request."
                )

            if (
                self.attachment.attachment_type
                != DiagnosticAttachment.AttachmentType.CLINICAL_IMAGE
            ):
                raise ValidationError(
                    "AI analysis requires a clinical image."
                )

    def __str__(self):
        return (
            f"{self.model.name} - "
            f"{self.diagnostic_request_id} - "
            f"{self.status}"
        )