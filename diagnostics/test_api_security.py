from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User, PatientProfile, DoctorProfile
from organizations.models import DiagnosticCenter, CenterMembership
from patients.models import DoctorPatientRelationship
import uuid
from diagnostics.models import (
    DiagnosticService,
    DiagnosticRequest,
    DiagnosticReport,
)
from prescriptions.models import Prescription


class MediBridgeAuthorizationTests(APITestCase):

    def setUp(self):
        # Patients
        self.patient_user = User.objects.create_user(
            email="patient-a@test.local",
            password="TestPassword123!",
            role=User.Role.PATIENT,
        )
        self.patient = PatientProfile.objects.create(
            user=self.patient_user,
        )

        self.other_patient_user = User.objects.create_user(
            email="patient-b@test.local",
            password="TestPassword123!",
            role=User.Role.PATIENT,
        )
        self.other_patient = PatientProfile.objects.create(
            user=self.other_patient_user,
        )

        # Doctors
        self.doctor_user = User.objects.create_user(
            email="doctor-a@test.local",
            password="TestPassword123!",
            role=User.Role.DOCTOR,
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="TEST-LIC-001",
            specialization="General Medicine",
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
        )

        self.other_doctor_user = User.objects.create_user(
            email="doctor-b@test.local",
            password="TestPassword123!",
            role=User.Role.DOCTOR,
        )
        self.other_doctor = DoctorProfile.objects.create(
            user=self.other_doctor_user,
            license_number="TEST-LIC-002",
            specialization="General Medicine",
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
        )

        # Diagnostic centers
        self.center_a = DiagnosticCenter.objects.create(
            name="Test Diagnostic Center A",
            registration_number="TEST-CENTER-A",
            email="center-a@test.local",
            phone="+8801700000001",
            address="Test Address A",
            verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
        )

        self.center_b = DiagnosticCenter.objects.create(
            name="Test Diagnostic Center B",
            registration_number="TEST-CENTER-B",
            email="center-b@test.local",
            phone="+8801700000002",
            address="Test Address B",
            verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
        )

        self.staff_user = User.objects.create_user(
            email="staff-a@test.local",
            password="TestPassword123!",
            role=User.Role.DIAGNOSTIC_STAFF,
        )

        CenterMembership.objects.create(
            user=self.staff_user,
            center=self.center_a,
            staff_role=CenterMembership.StaffRole.REPORT_VERIFIER,
            status=CenterMembership.Status.ACTIVE,
        )

        # Diagnostic requests
        self.request_a = self.make_request(
            self.center_a,
            self.patient,
            DiagnosticRequest.Status.COMPLETED,
        )

        self.request_b = self.make_request(
            self.center_a,
            self.other_patient,
            DiagnosticRequest.Status.COMPLETED,
        )

        # Released reports
        self.report_a = DiagnosticReport.objects.create(
            request=self.request_a,
            findings={"examination": "Test examination"},
            impression="Test impression",
            prepared_by=self.staff_user,
            status=DiagnosticReport.Status.RELEASED,
            released_at=timezone.now(),
        )

        self.report_b = DiagnosticReport.objects.create(
            request=self.request_b,
            findings={"examination": "Test examination"},
            impression="Test impression",
            prepared_by=self.staff_user,
            status=DiagnosticReport.Status.RELEASED,
            released_at=timezone.now(),
        )

        # Issued prescriptions
        self.prescription_a = Prescription.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            status=Prescription.Status.ISSUED,
            issued_at=timezone.now(),
        )

        self.prescription_b = Prescription.objects.create(
            patient=self.other_patient,
            doctor=self.doctor,
            status=Prescription.Status.ISSUED,
            issued_at=timezone.now(),
        )

    def make_request(self, center, patient, request_status):
        service = DiagnosticService.objects.create(
            center=center,
            service_code=f"TEST-{uuid.uuid4().hex[:12].upper()}",
            name="Test Diagnostic Service",
            category="Test",
            is_active=True,
        )

        return DiagnosticRequest.objects.create(
            patient=patient,
            service=service,
            requested_by=patient.user,
            status=request_status,
        )

    def authenticate_as(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def test_patient_cannot_access_another_patients_report(self):
        self.authenticate_as(self.patient_user)

        response = self.client.get(
            f"/api/diagnostics/reports/{self.report_b.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_patient_can_access_own_released_report(self):
        self.authenticate_as(self.patient_user)

        response = self.client.get(
            f"/api/diagnostics/reports/{self.report_a.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_patient_cannot_download_another_patients_prescription(self):
        self.authenticate_as(self.patient_user)

        response = self.client.get(
            f"/api/prescriptions/{self.prescription_b.id}/download/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_patient_can_download_own_issued_prescription(self):
        self.authenticate_as(self.patient_user)

        response = self.client.get(
            f"/api/prescriptions/{self.prescription_a.id}/download/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

    def test_unrelated_doctor_cannot_access_patient_report(self):
        self.authenticate_as(self.other_doctor_user)

        response = self.client.get(
            f"/api/diagnostics/reports/{self.report_a.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_doctor_with_active_relationship_can_access_report(self):
        DoctorPatientRelationship.objects.create(
            patient=self.patient,
            doctor=self.other_doctor,
            initiated_by=self.patient_user,
            status=DoctorPatientRelationship.Status.ACTIVE,
            started_at=timezone.now(),
        )

        self.authenticate_as(self.other_doctor_user)

        response = self.client.get(
            f"/api/diagnostics/reports/{self.report_a.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_diagnostic_staff_cannot_access_another_centers_request(self):
        request_at_center_b = self.make_request(
            self.center_b,
            self.patient,
            DiagnosticRequest.Status.REQUESTED,
        )

        self.authenticate_as(self.staff_user)

        response = self.client.get(
            f"/api/diagnostics/requests/{request_at_center_b.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_report_preparer_cannot_verify_own_report(self):
        pending_request = self.make_request(
            self.center_a,
            self.patient,
            DiagnosticRequest.Status.REPORT_PENDING,
        )

        submitted_report = DiagnosticReport.objects.create(
            request=pending_request,
            findings={"examination": "Test examination"},
            impression="Test impression",
            prepared_by=self.staff_user,
            status=DiagnosticReport.Status.SUBMITTED,
        )

        self.authenticate_as(self.staff_user)

        response = self.client.post(
            f"/api/diagnostics/reports/{submitted_report.id}/verify/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_patient_cannot_access_unreleased_report(self):
        pending_request = self.make_request(
            self.center_a,
            self.patient,
            DiagnosticRequest.Status.REPORT_PENDING,
        )

        submitted_report = DiagnosticReport.objects.create(
            request=pending_request,
            findings={"examination": "Test examination"},
            impression="Test impression",
            prepared_by=self.staff_user,
            status=DiagnosticReport.Status.SUBMITTED,
        )

        self.authenticate_as(self.patient_user)

        response = self.client.get(
            f"/api/diagnostics/reports/{submitted_report.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_access_report(self):
        response = self.client.get(
            f"/api/diagnostics/reports/{self.report_a.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
