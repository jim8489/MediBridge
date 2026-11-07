from django.db import transaction
from rest_framework import serializers

from accounts.models import DoctorProfile, PatientProfile, User
from patients.models import Consultation, DoctorPatientRelationship
from .models import Prescription, PrescriptionItem


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ("id", "medication_name", "generic_name", "strength", "dosage", "route", "frequency", "duration", "quantity", "instructions")
        read_only_fields = ("id",)


class PrescriptionSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    doctor_name = serializers.CharField(source="doctor.user.get_full_name", read_only=True)

    class Meta:
        model = Prescription
        fields = (
            "id", "prescription_number", "patient", "patient_number", "doctor", "doctor_name",
            "consultation", "items", "status", "general_instructions", "valid_until",
            "issued_at", "created_at",
        )
        read_only_fields = ("id", "prescription_number", "doctor", "status", "issued_at", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.role != User.Role.DOCTOR:
            raise serializers.ValidationError("Only doctors can create prescriptions.")
        doctor = getattr(request.user, "doctor_profile", None)
        if not doctor or doctor.verification_status != DoctorProfile.VerificationStatus.APPROVED:
            raise serializers.ValidationError("An approved doctor profile is required.")
        patient = attrs.get("patient")
        if not DoctorPatientRelationship.objects.filter(
            patient=patient, doctor=doctor, status=DoctorPatientRelationship.Status.ACTIVE
        ).exists():
            raise serializers.ValidationError({"patient": "You do not have an active care relationship with this patient."})
        consultation = attrs.get("consultation")
        if consultation and (
            consultation.patient_id != patient.id
            or consultation.doctor_id != doctor.id
            or consultation.status != Consultation.Status.SIGNED
        ):
            raise serializers.ValidationError({"consultation": "Select a signed consultation belonging to this doctor and patient."})
        items = attrs.get("items", [])
        if not items:
            raise serializers.ValidationError({"items": "At least one medication item is required."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        validated_data["doctor"] = self.context["request"].user.doctor_profile
        prescription = Prescription.objects.create(**validated_data)
        PrescriptionItem.objects.bulk_create([
            PrescriptionItem(prescription=prescription, **item_data) for item_data in items_data
        ])
        return prescription
