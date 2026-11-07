import uuid

from django.conf import settings
from django.db import models


class DiagnosticCenter(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending verification"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100, unique=True)
    email = models.EmailField()
    phone = models.CharField(max_length=25)
    address = models.TextField()
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CenterMembership(models.Model):
    class StaffRole(models.TextChoices):
        OWNER = "OWNER", "Owner"
        CENTER_ADMIN = "CENTER_ADMIN", "Center administrator"
        TECHNICIAN = "TECHNICIAN", "Technician"
        REPORT_VERIFIER = "REPORT_VERIFIER", "Report verifier"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        REVOKED = "REVOKED", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    center = models.ForeignKey(DiagnosticCenter, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="center_memberships")
    staff_role = models.CharField(max_length=20, choices=StaffRole.choices, default=StaffRole.TECHNICIAN)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    joined_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("center", "user"), name="unique_center_user_membership")]
        indexes = [models.Index(fields=("user", "status")), models.Index(fields=("center", "status"))]

    def __str__(self):
        return f"{self.user.email} @ {self.center.name}"
