from django import forms
from django.contrib import admin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import DoctorProfile, PatientProfile, User


class MediBridgeUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "role", "is_staff", "is_superuser", "is_active")


class MediBridgeUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class PatientProfileInline(admin.StackedInline):
    model = PatientProfile
    can_delete = False
    extra = 0


class DoctorProfileInline(admin.StackedInline):
    model = DoctorProfile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = MediBridgeUserChangeForm
    add_form = MediBridgeUserCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name", "phone")}),
        ("Role and permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "role", "password1", "password2", "is_staff", "is_superuser", "is_active")}),
    )
    filter_horizontal = ("groups", "user_permissions")
    inlines = (PatientProfileInline, DoctorProfileInline)

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)
