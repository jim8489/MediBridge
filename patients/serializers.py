from django.utils import timezone
from rest_framework import serializers

from accounts.models import DoctorProfile, PatientProfile, User
from .models import Consultation, DoctorPatientRelationship, Observation


class DoctorPatientRelationshipSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source="doctor.user.get_full_name", read_only=True)
    doctor_specialization = serializers.CharField(source="doctor.specialization", read_only=True)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)

    class Meta:
        model = DoctorPatientRelationship
        fields = (
            "id", "patient", "patient_number", "doctor", "doctor_name",
            "doctor_specialization", "relationship_type", "status",
            "initiated_by", "started_at", "ended_at", "created_at",
        )
        read_only_fields = ("id", "patient", "status", "initiated_by", "started_at", "ended_at", "created_at")


class RelationshipCreateSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=DoctorProfile.objects.select_related("user"))
    relationship_type = serializers.ChoiceField(choices=DoctorPatientRelationship.RelationshipType.choices, default="CONSULTING")

    def validate_doctor(self, doctor):
        if doctor.verification_status != DoctorProfile.VerificationStatus.APPROVED or not doctor.user.is_active:
            raise serializers.ValidationError("This doctor is not currently approved to provide services.")
        return doctor

    def create(self, validated_data):
        patient = self.context["request"].user.patient_profile
        return DoctorPatientRelationship.objects.create(
            patient=patient,
            doctor=validated_data["doctor"],
            relationship_type=validated_data["relationship_type"],
            initiated_by=self.context["request"].user,
        )


class ConsultationSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    doctor_name = serializers.CharField(source="doctor.user.get_full_name", read_only=True)

    class Meta:
        model = Consultation
        fields = (
            "id", "patient", "patient_number", "doctor", "doctor_name",
            "consultation_date", "chief_complaint", "symptoms",
            "clinical_findings", "assessment", "treatment_plan",
            "follow_up_notes", "status", "signed_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "doctor", "status", "signed_at", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        patient = attrs.get("patient")
        if request.user.role != User.Role.DOCTOR:
            raise serializers.ValidationError("Only doctors can create consultations.")
        doctor = getattr(request.user, "doctor_profile", None)
        if not doctor or doctor.verification_status != DoctorProfile.VerificationStatus.APPROVED:
            raise serializers.ValidationError("An approved doctor profile is required.")
        if patient and not DoctorPatientRelationship.objects.filter(
            patient=patient, doctor=doctor, status=DoctorPatientRelationship.Status.ACTIVE
        ).exists():
            raise serializers.ValidationError({"patient": "You do not have an active care relationship with this patient."})
        return attrs

    def create(self, validated_data):
        validated_data["doctor"] = self.context["request"].user.doctor_profile
        return super().create(validated_data)


class ObservationSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True)

    class Meta:
        model = Observation
        fields = (
            "id", "patient", "patient_number", "consultation", "code", "name",
            "numeric_value", "text_value", "unit", "reference_low", "reference_high",
            "effective_at", "source", "recorded_by", "recorded_by_email", "created_at",
        )
        read_only_fields = ("id", "source", "recorded_by", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        patient = attrs.get("patient")
        consultation = attrs.get("consultation")
        if attrs.get("numeric_value") is None and not attrs.get("text_value", "").strip():
            raise serializers.ValidationError("Provide either numeric_value or text_value.")
        if attrs.get("numeric_value") is not None and attrs.get("text_value", "").strip():
            raise serializers.ValidationError("Provide either numeric_value or text_value, not both.")

        if request.user.role == User.Role.PATIENT:
            if patient != request.user.patient_profile:
                raise serializers.ValidationError({"patient": "You can only add observations to your own record."})
            if consultation:
                raise serializers.ValidationError({"consultation": "Patients cannot attach observations to a doctor's consultation."})
        elif request.user.role == User.Role.DOCTOR:
            doctor = getattr(request.user, "doctor_profile", None)
            if not doctor or doctor.verification_status != DoctorProfile.VerificationStatus.APPROVED:
                raise serializers.ValidationError("An approved doctor profile is required.")
            if not DoctorPatientRelationship.objects.filter(
                patient=patient, doctor=doctor, status=DoctorPatientRelationship.Status.ACTIVE
            ).exists():
                raise serializers.ValidationError({"patient": "You do not have an active care relationship with this patient."})
            if consultation and (consultation.patient_id != patient.id or consultation.doctor_id != doctor.id):
                raise serializers.ValidationError({"consultation": "The consultation must belong to this doctor and patient."})
            if consultation and consultation.status != Consultation.Status.SIGNED:
                raise serializers.ValidationError({"consultation": "Observations can only be attached to a signed consultation."})
        else:
            raise serializers.ValidationError("Only patients and approved doctors can add observations.")
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["recorded_by"] = user
        validated_data["source"] = (
            Observation.Source.PATIENT_REPORTED
            if user.role == User.Role.PATIENT
            else Observation.Source.CLINICIAN
        )
        return super().create(validated_data)
