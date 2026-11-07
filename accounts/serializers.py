from django.db import transaction
from rest_framework import serializers

from .models import DoctorProfile, PatientProfile, User


class PatientRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone", "password", "password_confirm")

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "The passwords do not match."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            role=User.Role.PATIENT,
            **validated_data,
        )
        PatientProfile.objects.create(user=user)
        return user


class PatientProfileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ("id", "patient_number", "date_of_birth", "sex", "blood_group")


class DoctorProfileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = ("id", "license_number", "specialization", "verification_status")


class CurrentUserSerializer(serializers.ModelSerializer):
    patient_profile = serializers.SerializerMethodField()
    doctor_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "phone", "role", "patient_profile", "doctor_profile")

    def get_patient_profile(self, obj):
        profile = getattr(obj, "patient_profile", None)
        return PatientProfileSummarySerializer(profile).data if profile else None

    def get_doctor_profile(self, obj):
        profile = getattr(obj, "doctor_profile", None)
        return DoctorProfileSummarySerializer(profile).data if profile else None
