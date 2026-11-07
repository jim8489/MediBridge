from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CurrentUserSerializer, PatientRegistrationSerializer
from .token import MediBridgeTokenObtainPairSerializer


class PatientRegistrationView(generics.CreateAPIView):
    """Public registration endpoint. It always creates a PATIENT account."""
    serializer_class = PatientRegistrationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(summary="Register a patient", tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MediBridgeTokenObtainPairView(TokenObtainPairView):
    serializer_class = MediBridgeTokenObtainPairSerializer


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
