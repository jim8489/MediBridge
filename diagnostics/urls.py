from rest_framework.routers import DefaultRouter
from .views import DiagnosticReportViewSet, DiagnosticRequestViewSet, DiagnosticServiceViewSet

router = DefaultRouter()
router.register("services", DiagnosticServiceViewSet, basename="diagnostic-service")
router.register("requests", DiagnosticRequestViewSet, basename="diagnostic-request")
router.register("reports", DiagnosticReportViewSet, basename="diagnostic-report")

urlpatterns = router.urls
