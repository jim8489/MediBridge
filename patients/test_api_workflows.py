from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, PatientProfile, DoctorProfile
from patients.models import (
    DoctorPatientRelationship,
    Consultation,
    Observation,
)


class PatientDoctorWorkflowAPITests(APITestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(
            email="workflow-patient@test.local",
            password="TestPassword123!",
            role=User.Role.PATIENT,
        )
        self.patient = PatientProfile.objects.create(user=self.patient_user)

        self.other_patient_user = User.objects.create_user(
            email="workflow-other-patient@test.local",
            password="TestPassword123!",
            role=User.Role.PATIENT,
        )
        self.other_patient = PatientProfile.objects.create(
            user=self.other_patient_user
        )

        self.doctor_user = User.objects.create_user(
            email="workflow-doctor@test.local",
            password="TestPassword123!",
            role=User.Role.DOCTOR,
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="WORKFLOW-LIC-001",
            specialization="General Medicine",
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
        )

        self.other_doctor_user = User.objects.create_user(
            email="workflow-other-doctor@test.local",
            password="TestPassword123!",
            role=User.Role.DOCTOR,
        )
        self.other_doctor = DoctorProfile.objects.create(
            user=self.other_doctor_user,
            license_number="WORKFLOW-LIC-002",
            specialization="General Medicine",
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
        )

        self.staff_user = User.objects.create_user(
            email="workflow-staff@test.local",
            password="TestPassword123!",
            role=User.Role.DIAGNOSTIC_STAFF,
        )

        self.relationship_url = "/api/medical-records/relationships/"
        self.consultation_url = "/api/medical-records/consultations/"
        self.observation_url = "/api/medical-records/observations/"

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_active_relationship(self, patient=None, doctor=None):
        return DoctorPatientRelationship.objects.create(
            patient=patient or self.patient,
            doctor=doctor or self.doctor,
            initiated_by=(patient or self.patient).user,
            status=DoctorPatientRelationship.Status.ACTIVE,
            started_at=timezone.now(),
        )

    def test_patient_can_request_doctor_and_doctor_can_accept(self):
        self.authenticate(self.patient_user)

        response = self.client.post(
            self.relationship_url,
            {
                "doctor": str(self.doctor.id),
                "relationship_type": "CONSULTING",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        relationship_id = response.data["id"]
        self.assertEqual(response.data["status"], "PENDING")

        # An unrelated doctor must not accept this request.
        self.authenticate(self.other_doctor_user)
        response = self.client.post(
            f"{self.relationship_url}{relationship_id}/accept/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # The requested doctor can accept it.
        self.authenticate(self.doctor_user)
        response = self.client.post(
            f"{self.relationship_url}{relationship_id}/accept/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ACTIVE")

    def test_only_patient_or_connected_doctor_can_revoke_relationship(self):
        relationship = self.create_active_relationship()

        self.authenticate(self.other_doctor_user)
        response = self.client.post(
            f"{self.relationship_url}{relationship.id}/revoke/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.patient_user)
        response = self.client.post(
            f"{self.relationship_url}{relationship.id}/revoke/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "REVOKED")

    def test_connected_doctor_can_revoke_relationship(self):
        relationship = self.create_active_relationship()

        self.authenticate(self.doctor_user)
        response = self.client.post(
            f"{self.relationship_url}{relationship.id}/revoke/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "REVOKED")

    def test_doctor_cannot_initiate_patient_relationship(self):
        self.authenticate(self.doctor_user)

        response = self.client.post(
            self.relationship_url,
            {
                "doctor": str(self.doctor.id),
                "relationship_type": "CONSULTING",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_connected_doctor_can_create_sign_and_patient_can_view_consultation(self):
        self.create_active_relationship()

        self.authenticate(self.doctor_user)
        response = self.client.post(
            self.consultation_url,
            {
                "patient": str(self.patient.id),
                "chief_complaint": "Persistent cough",
                "symptoms": "Cough and mild fever",
                "assessment": "Clinical assessment",
                "treatment_plan": "Follow-up required",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        consultation_id = response.data["id"]
        self.assertEqual(response.data["status"], "DRAFT")

        # The doctor signs the consultation.
        response = self.client.post(
            f"{self.consultation_url}{consultation_id}/sign/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SIGNED")

        # The patient can now view the signed consultation.
        self.authenticate(self.patient_user)
        response = self.client.get(
            f"{self.consultation_url}{consultation_id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Another patient cannot view it.
        self.authenticate(self.other_patient_user)
        response = self.client.get(
            f"{self.consultation_url}{consultation_id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # An unrelated doctor cannot view it either.
        self.authenticate(self.other_doctor_user)
        response = self.client.get(
            f"{self.consultation_url}{consultation_id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_without_active_relationship_cannot_create_consultation(self):
        self.authenticate(self.doctor_user)

        response = self.client.post(
            self.consultation_url,
            {
                "patient": str(self.patient.id),
                "chief_complaint": "Test consultation",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patient_cannot_create_doctor_consultation(self):
        self.authenticate(self.patient_user)

        response = self.client.post(
            self.consultation_url,
            {
                "patient": str(self.patient.id),
                "chief_complaint": "Test consultation",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_can_only_add_observation_to_own_record(self):
        self.authenticate(self.patient_user)

        own_response = self.client.post(
            self.observation_url,
            {
                "patient": str(self.patient.id),
                "name": "Body temperature",
                "numeric_value": "37.2",
                "unit": "C",
            },
            format="json",
        )
        self.assertEqual(own_response.status_code, status.HTTP_201_CREATED)

        other_response = self.client.post(
            self.observation_url,
            {
                "patient": str(self.other_patient.id),
                "name": "Body temperature",
                "numeric_value": "37.2",
                "unit": "C",
            },
            format="json",
        )
        self.assertEqual(
            other_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        observation_id = own_response.data["id"]

        self.authenticate(self.other_patient_user)
        response = self.client.get(
            f"{self.observation_url}{observation_id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_needs_active_relationship_to_record_observation(self):
        self.authenticate(self.doctor_user)

        response = self.client.post(
            self.observation_url,
            {
                "patient": str(self.patient.id),
                "name": "Blood pressure",
                "numeric_value": "120",
                "unit": "mmHg",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.create_active_relationship()

        response = self.client.post(
            self.observation_url,
            {
                "patient": str(self.patient.id),
                "name": "Blood pressure",
                "numeric_value": "120",
                "unit": "mmHg",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        observation_id = response.data["id"]

        # The unrelated doctor cannot retrieve this observation.
        self.authenticate(self.other_doctor_user)
        response = self.client.get(
            f"{self.observation_url}{observation_id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_diagnostic_staff_cannot_access_medical_record_workflows(self):
        self.authenticate(self.staff_user)

        response = self.client.post(
            self.relationship_url,
            {
                "doctor": str(self.doctor.id),
                "relationship_type": "CONSULTING",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.post(
            self.consultation_url,
            {
                "patient": str(self.patient.id),
                "chief_complaint": "Test consultation",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get(self.observation_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
    def test_medical_record_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        for url in (
            self.relationship_url,
            self.consultation_url,
            self.observation_url,
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )