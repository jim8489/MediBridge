import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile
from patients.models import Consultation


class Prescription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription_number = models.CharField(max_length=32, unique=True, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="prescriptions")
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name="prescriptions")
    consultation = models.ForeignKey(Consultation, on_delete=models.PROTECT, null=True, blank=True, related_name="prescriptions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    general_instructions = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.prescription_number:
            self.prescription_number = f"MB-RX-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("patient", "status")), models.Index(fields=("doctor", "created_at"))]

    def __str__(self):
        return f"{self.prescription_number} — {self.patient.patient_number}"


class PrescriptionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="items")
    medication_name = models.CharField(max_length=180)
    generic_name = models.CharField(max_length=180, blank=True)
    strength = models.CharField(max_length=80, blank=True)
    dosage = models.CharField(max_length=100)
    route = models.CharField(max_length=40, blank=True)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    quantity = models.CharField(max_length=80, blank=True)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.medication_name} ({self.dosage})"
