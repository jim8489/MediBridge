import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile
from organizations.models import DiagnosticCenter


class DoctorPatientRelationship(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"

    class RelationshipType(models.TextChoices):
        PRIMARY = "PRIMARY", "Primary care"
        CONSULTING = "CONSULTING", "Consulting"
        FOLLOW_UP = "FOLLOW_UP", "Follow-up"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="doctor_relationships")
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name="patient_relationships")
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="initiated_care_relationships")
    relationship_type = models.CharField(max_length=16, choices=RelationshipType.choices, default=RelationshipType.CONSULTING)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("patient", "doctor"),
                condition=Q(status__in=("PENDING", "ACTIVE")),
                name="unique_pending_or_active_patient_doctor",
            )
        ]
        indexes = [models.Index(fields=("patient", "status")), models.Index(fields=("doctor", "status"))]

    def __str__(self):
        return f"{self.patient.patient_number} ↔ {self.doctor} ({self.status})"


class PatientConsent(models.Model):
    class Scope(models.TextChoices):
        MEDICAL_HISTORY = "MEDICAL_HISTORY", "Medical history"
        DIAGNOSTIC_REPORTS = "DIAGNOSTIC_REPORTS", "Diagnostic reports"
        CONSULTATIONS = "CONSULTATIONS", "Consultation records"
        TREATMENT_HISTORY = "TREATMENT_HISTORY", "Treatment history"
        DIAGNOSTIC_INVESTIGATION = "DIAGNOSTIC_INVESTIGATION", "Diagnostic investigation"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="consents")
    grantee_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="received_patient_consents")
    grantee_center = models.ForeignKey(DiagnosticCenter, on_delete=models.PROTECT, null=True, blank=True, related_name="received_patient_consents")
    scope = models.CharField(max_length=32, choices=Scope.choices)
    purpose = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(grantee_user__isnull=False) & Q(grantee_center__isnull=True))
                    | (Q(grantee_user__isnull=True) & Q(grantee_center__isnull=False))
                ),
                name="consent_has_exactly_one_grantee",
            )
        ]
        indexes = [models.Index(fields=("patient", "status")), models.Index(fields=("scope", "status"))]

    def __str__(self):
        recipient = self.grantee_user.email if self.grantee_user else self.grantee_center.name
        return f"Consent: {self.patient.patient_number} → {recipient} ({self.scope})"


class Consultation(models.Model):
    """A doctor's clinical encounter with a patient."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SIGNED = "SIGNED", "Signed"
        AMENDED = "AMENDED", "Amended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="consultations")
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name="consultations")
    consultation_date = models.DateTimeField(default=timezone.now)
    chief_complaint = models.TextField()
    symptoms = models.TextField(blank=True)
    clinical_findings = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    treatment_plan = models.TextField(blank=True)
    follow_up_notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-consultation_date",)
        indexes = [models.Index(fields=("patient", "consultation_date")), models.Index(fields=("doctor", "consultation_date"))]

    def __str__(self):
        return f"Consultation {self.id} — {self.patient.patient_number}"


class Observation(models.Model):
    """Structured clinical measurement or patient-reported observation."""

    class Source(models.TextChoices):
        CLINICIAN = "CLINICIAN", "Clinician recorded"
        PATIENT_REPORTED = "PATIENT_REPORTED", "Patient reported"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="observations")
    consultation = models.ForeignKey(Consultation, on_delete=models.PROTECT, null=True, blank=True, related_name="observations")
    code = models.CharField(max_length=80, blank=True, help_text="Optional standard code, e.g. LOINC")
    name = models.CharField(max_length=150)
    numeric_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    text_value = models.TextField(blank=True)
    unit = models.CharField(max_length=32, blank=True)
    reference_low = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    reference_high = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    effective_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=20, choices=Source.choices)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_observations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-effective_at",)
        indexes = [models.Index(fields=("patient", "name", "effective_at")), models.Index(fields=("patient", "code", "effective_at"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(numeric_value__isnull=False) | ~Q(text_value=""),
                name="observation_requires_a_value",
            )
        ]

    def __str__(self):
        value = self.numeric_value if self.numeric_value is not None else self.text_value[:30]
        return f"{self.patient.patient_number}: {self.name} = {value} {self.unit}".strip()
