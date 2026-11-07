from django.contrib import admin
from .models import DiagnosticReport, DiagnosticRequest, DiagnosticService


@admin.register(DiagnosticService)
class DiagnosticServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "center", "category", "requires_referral", "is_active")
    list_filter = ("category", "requires_referral", "is_active")
    search_fields = ("name", "service_code", "center__name")


@admin.register(DiagnosticRequest)
class DiagnosticRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "service", "status", "requested_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("patient__patient_number", "service__name", "requested_by__email")


@admin.register(DiagnosticReport)
class DiagnosticReportAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "status", "prepared_by", "verified_by", "submitted_at")
    list_filter = ("status", "submitted_at")
    search_fields = ("request__patient__patient_number", "impression")
