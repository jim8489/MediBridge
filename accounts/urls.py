from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CurrentUserView, MediBridgeTokenObtainPairView, PatientRegistrationView

urlpatterns = [
    path("register/", PatientRegistrationView.as_view(), name="patient-register"),
    path("token/", MediBridgeTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
]
