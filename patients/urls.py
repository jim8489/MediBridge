from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConsultationViewSet,
    DoctorPatientRelationshipListCreateView,
    ObservationViewSet,
    RelationshipActionView,
)

router = DefaultRouter()
router.register("consultations", ConsultationViewSet, basename="consultation")
router.register("observations", ObservationViewSet, basename="observation")

urlpatterns = [
    path("relationships/", DoctorPatientRelationshipListCreateView.as_view(), name="relationship-list-create"),
    path("relationships/<uuid:pk>/accept/", RelationshipActionView.as_view({"post": "accept"}), name="relationship-accept"),
    path("relationships/<uuid:pk>/revoke/", RelationshipActionView.as_view({"post": "revoke"}), name="relationship-revoke"),
    path("", include(router.urls)),
]
