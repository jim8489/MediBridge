from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PatientProfile, User


class PatientRegistrationTests(APITestCase):
    def test_public_registration_creates_patient_and_profile(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "rahim@example.com",
                "first_name": "Rahim",
                "last_name": "Ahmed",
                "phone": "+8801700000000",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="rahim@example.com")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())

    def test_registration_does_not_allow_role_escalation(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "attacker@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "role": "ADMIN",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="attacker@example.com")
        self.assertEqual(user.role, User.Role.PATIENT)

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "bad@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password": "StrongPassword123!",
                "password_confirm": "DifferentPassword123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
