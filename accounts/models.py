import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


def generate_patient_number():
    return f"MBP-{uuid.uuid4().hex[:10].upper()}"


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Patient"
        DOCTOR = "DOCTOR", "Doctor"
        DIAGNOSTIC_STAFF = "DIAGNOSTIC_STAFF", "Diagnostic staff"
        ADMIN = "ADMIN", "Administrator"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=25, blank=True)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.PATIENT)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class PatientProfile(models.Model):
    class Sex(models.TextChoices):
        FEMALE = "FEMALE", "Female"
        MALE = "MALE", "Male"
        OTHER = "OTHER", "Other"
        PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY", "Prefer not to say"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="patient_profile")
    patient_number = models.CharField(max_length=20, unique=True, default=generate_patient_number, editable=False)
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=20, choices=Sex.choices, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=25, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient_number} — {self.user.get_full_name() or self.user.email}"


class DoctorProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending verification"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="doctor_profile")
    license_number = models.CharField(max_length=80, unique=True)
    specialization = models.CharField(max_length=150)
    qualification = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    professional_bio = models.TextField(blank=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.email}"
