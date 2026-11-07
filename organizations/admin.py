from django.contrib import admin

from .models import CenterMembership, DiagnosticCenter


class CenterMembershipInline(admin.TabularInline):
    model = CenterMembership
    extra = 0


@admin.register(DiagnosticCenter)
class DiagnosticCenterAdmin(admin.ModelAdmin):
    list_display = ("name", "registration_number", "verification_status", "is_active", "created_at")
    list_filter = ("verification_status", "is_active")
    search_fields = ("name", "registration_number", "email")
    inlines = (CenterMembershipInline,)


@admin.register(CenterMembership)
class CenterMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "center", "staff_role", "status", "joined_at")
    list_filter = ("staff_role", "status")
    search_fields = ("user__email", "center__name")
