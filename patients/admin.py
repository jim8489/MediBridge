from django.contrib import admin

from .models import Consultation, DoctorPatientRelationship, Observation, PatientConsent


@admin.register(DoctorPatientRelationship)
class DoctorPatientRelationshipAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "relationship_type", "status", "created_at")
    list_filter = ("status", "relationship_type")
    search_fields = ("patient__patient_number", "doctor__user__email")


@admin.register(PatientConsent)
class PatientConsentAdmin(admin.ModelAdmin):
    list_display = ("patient", "scope", "status", "grantee_user", "grantee_center", "granted_at")
    list_filter = ("scope", "status")
    search_fields = ("patient__patient_number", "grantee_user__email", "grantee_center__name")


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "consultation_date", "status")
    list_filter = ("status", "consultation_date")
    search_fields = ("patient__patient_number", "doctor__user__email", "chief_complaint")


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ("patient", "name", "numeric_value", "unit", "effective_at", "source")
    list_filter = ("source", "effective_at")
    search_fields = ("patient__patient_number", "name", "code")
