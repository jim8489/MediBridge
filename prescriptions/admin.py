from django.contrib import admin
from .models import Prescription, PrescriptionItem


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 0


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("prescription_number", "patient", "doctor", "status", "issued_at")
    list_filter = ("status", "issued_at")
    search_fields = ("prescription_number", "patient__patient_number", "doctor__user__email")
    inlines = (PrescriptionItemInline,)
