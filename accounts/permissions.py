from rest_framework.permissions import BasePermission

from .models import DoctorProfile, User


class IsPatient(BasePermission):
    message = "This action is available to patient accounts only."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.PATIENT)


class IsApprovedDoctor(BasePermission):
    message = "An approved doctor account is required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or user.role != User.Role.DOCTOR:
            return False
        try:
            return user.doctor_profile.verification_status == DoctorProfile.VerificationStatus.APPROVED
        except DoctorProfile.DoesNotExist:
            return False


class IsDiagnosticStaff(BasePermission):
    message = "A diagnostic-center staff account is required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or user.role != User.Role.DIAGNOSTIC_STAFF:
            return False
        return user.center_memberships.filter(status="ACTIVE", center__verification_status="APPROVED").exists()
