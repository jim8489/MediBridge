from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser
from django.http import FileResponse
from django.shortcuts import get_object_or_404
import logging
from drf_spectacular.types import OpenApiTypes

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from accounts.models import User
from organizations.models import CenterMembership, DiagnosticCenter
from patients.models import DoctorPatientRelationship
from .models import AIAnalysis, DiagnosticAttachment, DiagnosticReport, DiagnosticRequest, DiagnosticService
from .serializers import (
    DiagnosticAttachmentSerializer,
    DiagnosticReportCreateSerializer,
    DiagnosticReportReadSerializer,
    DiagnosticRequestSerializer,
    DiagnosticServiceSerializer,
    AIAnalysisReadSerializer,
    AIAnalysisRequestSerializer,
    AIAnalysisReviewSerializer,
)
from .ai.inference import predict_attachment
from .ai.registry import get_registered_model
logger = logging.getLogger(__name__)



def active_membership(user, center):
    return CenterMembership.objects.filter(
        user=user,
        center=center,
        status=CenterMembership.Status.ACTIVE,
        center__is_active=True,
        center__verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
    ).first()


def is_report_verifier(membership):
    return bool(membership and membership.staff_role in (
        CenterMembership.StaffRole.OWNER,
        CenterMembership.StaffRole.CENTER_ADMIN,
        CenterMembership.StaffRole.REPORT_VERIFIER,
    ))


class DiagnosticServiceViewSet(viewsets.ModelViewSet):
    serializer_class = DiagnosticServiceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DiagnosticService.objects.select_related("center").filter(
            is_active=True,
            center__is_active=True,
            center__verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
        )
        user = self.request.user
        if user.role == User.Role.DIAGNOSTIC_STAFF:
            center_ids = user.center_memberships.filter(status=CenterMembership.Status.ACTIVE).values_list("center_id", flat=True)
            # Staff may discover public services and their own center's services.
            return qs
        return qs

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.DIAGNOSTIC_STAFF:
            raise PermissionDenied("Only diagnostic-center staff can create services.")
        return super().create(request, *args, **kwargs)


class DiagnosticRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DiagnosticRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = DiagnosticRequest.objects.select_related(
            "patient__user", "service__center", "requested_by", "ordering_doctor__user"
        )
        if user.role == User.Role.PATIENT:
            return qs.filter(patient__user=user)
        if user.role == User.Role.DOCTOR:
            return qs.filter(
                ordering_doctor__user=user
            ) | qs.filter(
                patient__doctor_relationships__doctor__user=user,
                patient__doctor_relationships__status=DoctorPatientRelationship.Status.ACTIVE,
                status=DiagnosticRequest.Status.COMPLETED,
            )
        if user.role == User.Role.DIAGNOSTIC_STAFF:
            center_ids = user.center_memberships.filter(
                status=CenterMembership.Status.ACTIVE,
                center__is_active=True,
                center__verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
            ).values_list("center_id", flat=True)
            return qs.filter(service__center_id__in=center_ids)
        if user.is_staff:
            return qs
        return qs.none()

    def create(self, request, *args, **kwargs):
        if request.user.role not in (User.Role.PATIENT, User.Role.DOCTOR):
            raise PermissionDenied("Only patients and doctors can submit diagnostic requests.")
        return super().create(request, *args, **kwargs)

    def _require_center_staff(self, diagnostic_request):
        membership = active_membership(self.request.user, diagnostic_request.service.center)
        if not membership:
            raise PermissionDenied("You are not an active staff member of the assigned diagnostic center.")
        return membership

    @extend_schema(
        request=None,
        responses={200: DiagnosticRequestSerializer},
        summary="Accept a diagnostic request",
        tags=["Diagnostics"],
    )
    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        diagnostic_request = self.get_object()
        self._require_center_staff(diagnostic_request)
        if diagnostic_request.status != DiagnosticRequest.Status.REQUESTED:
            raise ValidationError("Only requested investigations can be accepted.")
        diagnostic_request.status = DiagnosticRequest.Status.ACCEPTED
        diagnostic_request.accepted_at = timezone.now()
        diagnostic_request.save(update_fields=["status", "accepted_at", "updated_at"])
        return Response(self.get_serializer(diagnostic_request).data)

    @extend_schema(
        request=None,
        responses={200: DiagnosticRequestSerializer},
        summary="Start a diagnostic investigation",
        tags=["Diagnostics"],
    )
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        diagnostic_request = self.get_object()
        self._require_center_staff(diagnostic_request)
        if diagnostic_request.status != DiagnosticRequest.Status.ACCEPTED:
            raise ValidationError("Only accepted investigations can be started.")
        diagnostic_request.status = DiagnosticRequest.Status.IN_PROGRESS
        diagnostic_request.started_at = timezone.now()
        diagnostic_request.save(update_fields=["status", "started_at", "updated_at"])
        return Response(self.get_serializer(diagnostic_request).data)
    @extend_schema(
        operation_id="upload_diagnostic_attachment",
        summary="Upload a diagnostic image or document",
        description=(
            "Upload a JPEG, PNG or PDF attachment "
            "to an ongoing diagnostic investigation."
        ),
        request=DiagnosticAttachmentSerializer,
        responses={
            201: DiagnosticAttachmentSerializer,
        },
        tags=["Diagnostics"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="attachments",
        parser_classes=[MultiPartParser],
        serializer_class=DiagnosticAttachmentSerializer,
    )
    def upload_attachment(self, request, pk=None):
        """
        Upload an image or document for an ongoing diagnostic request.
        """

        diagnostic_request = self.get_object()

        self._require_center_staff(diagnostic_request)

        if diagnostic_request.status != DiagnosticRequest.Status.IN_PROGRESS:
            raise ValidationError(
                "Files can only be uploaded for investigations in progress."
            )

        serializer = DiagnosticAttachmentSerializer(
            data=request.data,
            context={
                **self.get_serializer_context(),
                "diagnostic_request": diagnostic_request,
            },
        )

        serializer.is_valid(raise_exception=True)

        attachment = serializer.save()

        return Response(
            DiagnosticAttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        operation_id="download_diagnostic_attachment",
        summary="Download a diagnostic attachment securely",
        description=(
            "Downloads an attachment after checking patient ownership, "
            "doctor-patient authorization, or diagnostic-center membership."
        ),
        responses={
            (200, "image/jpeg"): OpenApiTypes.BINARY,
            (200, "image/png"): OpenApiTypes.BINARY,
            (200, "application/pdf"): OpenApiTypes.BINARY,
            (200, "application/octet-stream"): OpenApiTypes.BINARY,
        },
        tags=["Diagnostics"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"attachments/(?P<attachment_id>[^/.]+)/download",
        url_name="download-attachment",
    )
    def download_attachment(self, request, pk=None, attachment_id=None):
        """
        Download a diagnostic attachment after authorization.
        """

        # Step 1: Retrieve a diagnostic request that this user
        # is already permitted to access.
        diagnostic_request = self.get_object()

        # Step 2: Retrieve the attachment belonging specifically
        # to this diagnostic request.
        attachment = get_object_or_404(
            DiagnosticAttachment.objects.select_related(
                "request",
                "request__patient__user",
                "request__service__center",
                "request__ordering_doctor__user",
                "request__report",
            ),
            pk=attachment_id,
            request=diagnostic_request,
        )

        user = request.user

        # Check whether the diagnostic report has been released.
        report = getattr(diagnostic_request, "report", None)

        report_is_released = (
            report is not None
            and report.status == DiagnosticReport.Status.RELEASED
        )

        # Step 3: Patient authorization.
        if user.role == User.Role.PATIENT:

            if (
                diagnostic_request.patient.user_id != user.id
                or not report_is_released
            ):
                raise PermissionDenied(
                    "You can only download your own released diagnostic files."
                )

        # Step 4: Doctor authorization.
        elif user.role == User.Role.DOCTOR:

            is_ordering_doctor = (
                diagnostic_request.ordering_doctor is not None
                and diagnostic_request.ordering_doctor.user_id == user.id
            )

            has_active_relationship = (
                DoctorPatientRelationship.objects.filter(
                    patient=diagnostic_request.patient,
                    doctor__user=user,
                    status=DoctorPatientRelationship.Status.ACTIVE,
                ).exists()
            )

            if (
                not report_is_released
                or not (
                    is_ordering_doctor
                    or has_active_relationship
                )
            ):
                raise PermissionDenied(
                    "You are not authorized to download this diagnostic file."
                )

        # Step 5: Diagnostic-center staff authorization.
        elif user.role == User.Role.DIAGNOSTIC_STAFF:

            self._require_center_staff(diagnostic_request)

        # Step 6: Administrative access.
        elif not user.is_staff:

            raise PermissionDenied(
                "You are not authorized to download this file."
            )

        # Step 7: Open the file through the private storage backend.
        try:
            file_handle = attachment.file.open("rb")

        except (FileNotFoundError, OSError, ValueError):
            raise NotFound(
                "The diagnostic attachment file could not be found."
            )

        # Step 8: Stream the file instead of exposing its storage URL.
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=attachment.original_filename,
            content_type=(
                attachment.content_type
                or "application/octet-stream"
            ),
        )

        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"

        return response
    
    @extend_schema(
        operation_id="analyze_chest_xray",
        request=AIAnalysisRequestSerializer,
        responses={
            201: AIAnalysisReadSerializer,
        },
        summary="Analyze a chest X-ray using AI",
        description=(
            "Runs the registered TorchXRayVision model on a clinical "
            "chest X-ray attachment and stores its pathology scores."
        ),
        tags=["AI Diagnostics"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="analyze",
    )
    def analyze(self, request, pk=None):

        diagnostic_request = self.get_object()

        self._require_center_staff(diagnostic_request)

        service = diagnostic_request.service

        service_description = (
            f"{service.service_code} "
            f"{service.name} "
            f"{service.category}"
        ).lower().replace("_", " ").replace("-", " ")

        if (
            "chest" not in service_description
            or not any(
                term in service_description
                for term in ("x ray", "xray")
            )
        ):
            raise ValidationError(
                "TorchXRayVision can only analyze chest X-ray services."
            )

        if diagnostic_request.status != DiagnosticRequest.Status.IN_PROGRESS:
            raise ValidationError(
                "The diagnostic investigation must be in progress."
            )

        serializer = AIAnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        attachment = get_object_or_404(
            DiagnosticAttachment.objects.filter(
                request=diagnostic_request,
                attachment_type=(
                    DiagnosticAttachment.AttachmentType.CLINICAL_IMAGE
                ),
            ),
            pk=serializer.validated_data["attachment_id"],
        )

        try:
            database_model, runtime_model = get_registered_model()

        except Exception:
            logger.exception(
                "Unable to load or register the chest X-ray model."
            )
            return Response(
                {"detail": "The AI service is currently unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Create a traceable analysis record before inference.
        analysis = AIAnalysis.objects.create(
            diagnostic_request=diagnostic_request,
            attachment=attachment,
            model=database_model,
            submitted_by=request.user,
            status=AIAnalysis.Status.PROCESSING,
            started_at=timezone.now(),
        )

        try:
            result = predict_attachment(
                attachment,
                model=runtime_model,
            )

            pathology_scores = result.get("pathology_scores")

            if not isinstance(pathology_scores, dict) or not pathology_scores:
                raise ValueError(
                    "The AI model returned no pathology scores."
                )

            analysis.pathology_scores = pathology_scores
            analysis.score_semantics = result.get("score_semantics", "")

            analysis.model_output = {
                "model_key": result.get("model_key"),
                "model_version": result.get("model_version"),
                "weights": result.get("weights"),
                "image_metadata": result.get("image_metadata", {}),
                "output_count": result.get(
                    "output_count",
                    len(pathology_scores),
                ),
            }

            analysis.status = AIAnalysis.Status.COMPLETED
            analysis.completed_at = timezone.now()

            analysis.save(
                update_fields=[
                    "pathology_scores",
                    "score_semantics",
                    "model_output",
                    "status",
                    "completed_at",
                ]
            )

        except Exception:
            logger.exception(
                "Chest X-ray inference failed for analysis %s",
                analysis.id,
            )

            analysis.status = AIAnalysis.Status.FAILED
            analysis.error_message = (
                "AI inference failed. Check the application logs."
            )
            analysis.completed_at = timezone.now()

            analysis.save(
                update_fields=[
                    "status",
                    "error_message",
                    "completed_at",
                ]
            )

            return Response(
                {
                    "detail": "AI inference failed.",
                    "analysis_id": str(analysis.id),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            AIAnalysisReadSerializer(analysis).data,
            status=status.HTTP_201_CREATED,
        )
    @extend_schema(
        request=None,
        responses={
            200: AIAnalysisReadSerializer(many=True),
        },
        summary="Retrieve AI analysis history",
        tags=["AI Diagnostics"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="analyses",
    )
    def analyses(self, request, pk=None):

        diagnostic_request = self.get_object()

        user = request.user

        if user.role == User.Role.DIAGNOSTIC_STAFF:

            self._require_center_staff(diagnostic_request)

        elif user.role in (
            User.Role.PATIENT,
            User.Role.DOCTOR,
        ):

            report = getattr(
                diagnostic_request,
                "report",
                None,
            )

            if (
                report is None
                or report.status != DiagnosticReport.Status.RELEASED
            ):
                raise PermissionDenied(
                    "AI results are available only after report release."
                )

        elif not user.is_staff:

            raise PermissionDenied(
                "You are not authorized to access AI analysis history."
            )

        analyses = AIAnalysis.objects.filter(
            diagnostic_request=diagnostic_request
        ).select_related(
            "model",
            "attachment",
            "submitted_by",
            "reviewed_by",
        ).order_by("-created_at")

        serializer = AIAnalysisReadSerializer(
            analyses,
            many=True,
        )

        return Response(serializer.data)
    
    @extend_schema(
        request=AIAnalysisReviewSerializer,
        responses={
            200: AIAnalysisReadSerializer,
        },
        summary="Review an AI analysis",
        tags=["AI Diagnostics"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"analyses/(?P<analysis_id>[^/.]+)/review",
    )
    def review_analysis(self, request, pk=None, analysis_id=None):

        diagnostic_request = self.get_object()

        membership = self._require_center_staff(
            diagnostic_request
        )

        if not is_report_verifier(membership):
            raise PermissionDenied(
                "An authorized center report verifier is required."
            )

        analysis = get_object_or_404(
            AIAnalysis,
            pk=analysis_id,
            diagnostic_request=diagnostic_request,
        )

        if analysis.status != AIAnalysis.Status.COMPLETED:
            raise ValidationError(
                "Only completed AI analyses can be reviewed."
            )

        if analysis.review_status != AIAnalysis.ReviewStatus.PENDING:
            raise ValidationError(
                "This AI analysis has already been reviewed."
            )

        serializer = AIAnalysisReviewSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        analysis.review_status = (
            serializer.validated_data["review_status"]
        )

        analysis.review_notes = (
            serializer.validated_data.get("review_notes", "")
        )

        analysis.reviewed_by = request.user
        analysis.reviewed_at = timezone.now()

        analysis.save(
            update_fields=[
                "review_status",
                "review_notes",
                "reviewed_by",
                "reviewed_at",
            ]
        )

        return Response(
            AIAnalysisReadSerializer(analysis).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=DiagnosticReportCreateSerializer,
        responses={201: DiagnosticReportReadSerializer},
        tags=["Diagnostics"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="submit-report",
    )
    def submit_report(self, request, pk=None):

        diagnostic_request = self.get_object()

        self._require_center_staff(diagnostic_request)

        if diagnostic_request.status != DiagnosticRequest.Status.IN_PROGRESS:
            raise ValidationError(
                "The investigation must be in progress before a report can be submitted."
            )

        if hasattr(diagnostic_request, "report"):
            raise ValidationError(
                "A report has already been submitted for this request."
            )

        serializer = DiagnosticReportCreateSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        validated_data = dict(serializer.validated_data)

        ai_analysis_id = validated_data.pop(
            "ai_analysis_id",
            None,
        )

        selected_analysis = None

        # Validate and retrieve the optional AI analysis.
        if ai_analysis_id:

            selected_analysis = get_object_or_404(
                AIAnalysis.objects.select_related(
                    "model",
                    "attachment",
                    "reviewed_by",
                ).filter(
                    diagnostic_request=diagnostic_request,
                ),
                pk=ai_analysis_id,
            )

            if selected_analysis.status != AIAnalysis.Status.COMPLETED:
                raise ValidationError(
                    "Only completed AI analyses can be included."
                )

            if (
                selected_analysis.review_status
                != AIAnalysis.ReviewStatus.ACCEPTED
            ):
                raise ValidationError(
                    "The AI analysis must be accepted by a reviewer first."
                )

            if not selected_analysis.reviewed_by_id:
                raise ValidationError(
                    "The AI analysis has no recorded reviewer."
                )

            if not selected_analysis.pathology_scores:
                raise ValidationError(
                    "The AI analysis has no stored pathology scores."
                )

        # Preserve clinician-entered findings.
        findings = dict(validated_data["findings"])

        # Attach a snapshot of the reviewed AI output.
        if selected_analysis:

            reviewer = selected_analysis.reviewed_by

            reviewer_name = (
                reviewer.get_full_name().strip()
                or reviewer.email
            )

            reviewed_at = (
                timezone.localtime(
                    selected_analysis.reviewed_at
                ).isoformat()
                if selected_analysis.reviewed_at
                else None
            )

            findings["ai_assistance"] = {
                "analysis_id": str(selected_analysis.id),

                "model": selected_analysis.model.name,

                "model_version": selected_analysis.model.version,

                "attachment_id": str(
                    selected_analysis.attachment_id
                ),

                "attachment_filename": (
                    selected_analysis.attachment.original_filename
                ),

                "scores": selected_analysis.pathology_scores,

                "score_semantics": (
                    selected_analysis.score_semantics
                ),

                "review_status": (
                    selected_analysis.review_status
                ),

                "reviewed_by": reviewer_name,

                "reviewed_at": reviewed_at,

                "review_notes": selected_analysis.review_notes,

                "notice": (
                    "AI-generated decision-support results. "
                    "These scores are not a confirmed diagnosis "
                    "and must be interpreted by a qualified clinician."
                ),
            }

        validated_data["findings"] = findings

        with transaction.atomic():

            report = DiagnosticReport.objects.create(
                request=diagnostic_request,
                prepared_by=request.user,
                **validated_data,
            )

            diagnostic_request.status = (
                DiagnosticRequest.Status.REPORT_PENDING
            )

            diagnostic_request.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return Response(
            DiagnosticReportReadSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )
def pdf_safe_text(value):
    """
    Escape database content before inserting it into ReportLab paragraphs.
    """
    return escape(str(value)).replace("\n", "<br/>")


def flatten_findings(value, prefix=""):
    """
    Convert nested findings JSON into readable label/value pairs.
    """
    rows = []

    if isinstance(value, dict):
        for key, item in value.items():
            label = f"{prefix} - {key}" if prefix else str(key)
            rows.extend(flatten_findings(item, label))

    elif isinstance(value, list):
        for index, item in enumerate(value, start=1):
            label = f"{prefix} - Item {index}" if prefix else f"Item {index}"
            rows.extend(flatten_findings(item, label))

    else:
        label = prefix or "Finding"
        display_value = "Not recorded" if value is None else str(value)
        rows.append((label, display_value))

    return rows


def format_report_date(value):
    """
    Format dates using Django's configured local timezone.
    """
    if not value:
        return "Not recorded"

    return timezone.localtime(value).strftime(
        "%d %b %Y, %I:%M %p"
    )


def generate_diagnostic_report_pdf(report):
    """
    Generate a formatted PDF for a diagnostic report.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="MediBridge Diagnostic Report",
        author="MediBridge",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MediBridgeTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=5,
    )

    subtitle_style = ParagraphStyle(
        "MediBridgeSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey,
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "MediBridgeHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#17365D"),
        spaceBefore=12,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "MediBridgeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=14,
    )

    label_style = ParagraphStyle(
        "MediBridgeLabel",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    story = []

    # Report heading
    story.append(Paragraph("MediBridge", title_style))
    story.append(
        Paragraph("DIAGNOSTIC MEDICAL REPORT", subtitle_style)
    )

    # Report identification
    story.append(
        Paragraph("Report Information", heading_style)
    )

    prepared_by = (
        report.prepared_by.email
        if report.prepared_by_id
        else "Not recorded"
    )

    verified_by = (
        report.verified_by.email
        if report.verified_by_id
        else "Not recorded"
    )

    metadata = [
        ["Report ID", str(report.id)],
        ["Patient Number", report.request.patient.patient_number],
        ["Diagnostic Center", report.request.service.center.name],
        ["Investigation", report.request.service.name],
        ["Report Status", report.status],
        ["Prepared By", prepared_by],
        ["Verified By", verified_by],
        ["Submitted At", format_report_date(report.submitted_at)],
        ["Verified At", format_report_date(report.verified_at)],
        ["Released At", format_report_date(report.released_at)],
    ]

    metadata_table = Table(
        [
            [
                Paragraph(pdf_safe_text(label), label_style),
                Paragraph(pdf_safe_text(value), body_style),
            ]
            for label, value in metadata
        ],
        colWidths=[42 * mm, 125 * mm],
    )

    metadata_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F6")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )

    story.append(metadata_table)

    # Clinical findings
    story.append(
        Paragraph("Clinical Findings", heading_style)
    )
    findings = dict(report.findings or {})

    # Separate AI assistance from clinician-entered findings.
    ai_assistance = findings.pop("ai_assistance", None)

    # ---------------------------------------
    # Clinical findings
    # ---------------------------------------

    story.append(
        Paragraph("Clinical Findings", heading_style)
    )

    findings_rows = flatten_findings(findings)

    if findings_rows:

        findings_data = [[
            Paragraph("Finding", label_style),
            Paragraph("Recorded Result", label_style),
        ]]

        for label, value in findings_rows:

            findings_data.append([
                Paragraph(pdf_safe_text(label), body_style),
                Paragraph(pdf_safe_text(value), body_style),
            ])

        findings_table = Table(
            findings_data,
            colWidths=[65 * mm, 102 * mm],
            repeatRows=1,
        )

        findings_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#EAF0F6"),
                ),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])
        )

        story.append(findings_table)

    else:

        story.append(
            Paragraph(
                "No structured clinical findings were recorded.",
                body_style,
            )
        )

    # ---------------------------------------
    # AI decision-support results
    # ---------------------------------------

    if ai_assistance:

        story.append(
            Paragraph(
                "AI Decision-Support Results",
                heading_style,
            )
        )

        ai_metadata = [
            (
                "Model",
                ai_assistance.get("model", "Not recorded"),
            ),
            (
                "Model Version",
                ai_assistance.get("model_version", "Not recorded"),
            ),
            (
                "Source Image",
                ai_assistance.get("attachment_filename", "Not recorded"),
            ),
            (
                "Review Status",
                ai_assistance.get("review_status", "Not recorded"),
            ),
            (
                "Reviewed By",
                ai_assistance.get("reviewed_by", "Not recorded"),
            ),
            (
                "Reviewed At",
                ai_assistance.get("reviewed_at", "Not recorded"),
            ),
        ]

        ai_metadata_table = Table(
            [
                [
                    Paragraph(pdf_safe_text(label), label_style),
                    Paragraph(pdf_safe_text(value), body_style),
                ]
                for label, value in ai_metadata
            ],
            colWidths=[48 * mm, 119 * mm],
        )

        ai_metadata_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#EAF0F6"),
                ),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])
        )

        story.append(ai_metadata_table)

        story.append(Spacer(1, 8))

        score_rows = flatten_findings(
            ai_assistance.get("scores", {})
        )

        if score_rows:

            score_data = [[
                Paragraph("Model Output", label_style),
                Paragraph("Score", label_style),
            ]]

            for label, value in score_rows:

                score_data.append([
                    Paragraph(pdf_safe_text(label), body_style),
                    Paragraph(pdf_safe_text(value), body_style),
                ])

            score_table = Table(
                score_data,
                colWidths=[105 * mm, 62 * mm],
                repeatRows=1,
            )

            score_table.setStyle(
                TableStyle([
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#EAF0F6"),
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ])
            )

            story.append(score_table)

        story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                "<b>Score interpretation:</b> "
                + pdf_safe_text(
                    ai_assistance.get(
                        "score_semantics",
                        "Refer to the model's score semantics.",
                    )
                ),
                body_style,
            )
        )

        story.append(Spacer(1, 5))

        story.append(
            Paragraph(
                pdf_safe_text(
                    ai_assistance.get("notice", "")
                ),
                body_style,
            )
        )

        if ai_assistance.get("review_notes"):

            story.append(Spacer(1, 5))

            story.append(
                Paragraph(
                    "<b>AI Review Notes:</b> "
                    + pdf_safe_text(
                        ai_assistance["review_notes"]
                    ),
                    body_style,
                )
            )
    # Clinical impression
    story.append(
        Paragraph("Clinical Impression", heading_style)
    )

    story.append(
        Paragraph(
            pdf_safe_text(report.impression or "Not recorded"),
            body_style,
        )
    )

    # Disclaimer
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "<b>Important:</b> This document contains diagnostic "
            "information recorded and released by the diagnostic "
            "center. Clinical interpretation and treatment decisions "
            "should be made by a qualified healthcare professional.",
            body_style,
        )
    )

    # Footer
    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)

        canvas.drawString(
            18 * mm,
            10 * mm,
            "MediBridge | Confidential Medical Information",
        )

        canvas.drawRightString(
            A4[0] - 18 * mm,
            10 * mm,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    buffer.seek(0)

    return buffer


class DiagnosticReportViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DiagnosticReportReadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = DiagnosticReport.objects.select_related(
            "request__patient__user", "request__service__center", "request__ordering_doctor__user",
            "prepared_by", "verified_by",
        )
        if user.role == User.Role.PATIENT:
            return qs.filter(request__patient__user=user, status=DiagnosticReport.Status.RELEASED)
        if user.role == User.Role.DOCTOR:
            return qs.filter(
                request__ordering_doctor__user=user, status=DiagnosticReport.Status.RELEASED
            ) | qs.filter(
                request__patient__doctor_relationships__doctor__user=user,
                request__patient__doctor_relationships__status=DoctorPatientRelationship.Status.ACTIVE,
                status=DiagnosticReport.Status.RELEASED,
            )
        if user.role == User.Role.DIAGNOSTIC_STAFF:
            center_ids = user.center_memberships.filter(
                status=CenterMembership.Status.ACTIVE,
                center__is_active=True,
                center__verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
            ).values_list("center_id", flat=True)
            return qs.filter(request__service__center_id__in=center_ids)
        if user.is_staff:
            return qs
        return qs.none()
    @extend_schema(
        operation_id="download_diagnostic_report_pdf",
        summary="Download a released diagnostic report as PDF",
        responses={
            (200, "application/pdf"): OpenApiTypes.BINARY,
        },
        tags=["Diagnostics"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="download",
    )
    def download_pdf(self, request, pk=None):

        report = self.get_object()

        # Only released reports can be downloaded.
        if report.status != DiagnosticReport.Status.RELEASED:
            raise PermissionDenied(
                "Only released diagnostic reports can be downloaded."
            )

        pdf_file = generate_diagnostic_report_pdf(report)

        filename = (
            f"MediBridge_Report_{report.request.patient.patient_number}.pdf"
        )

        return FileResponse(
            pdf_file,
            as_attachment=True,
            filename=filename,
            content_type="application/pdf",
        )

    def _require_verifier(self, report):
        membership = active_membership(self.request.user, report.request.service.center)
        if not is_report_verifier(membership):
            raise PermissionDenied("An active center owner, administrator, or report verifier is required.")
        return membership

    @extend_schema(
        request=None,
        responses={200: DiagnosticReportReadSerializer},
        summary="Verify a submitted diagnostic report",
        tags=["Diagnostics"],
    )
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        report = self.get_object()
        self._require_verifier(report)
        if report.status != DiagnosticReport.Status.SUBMITTED:
            raise ValidationError("Only submitted reports can be verified.")
        if report.prepared_by_id == request.user.id:
            raise PermissionDenied("The person who prepared the report cannot verify their own report.")
        report.status = DiagnosticReport.Status.VERIFIED
        report.verified_by = request.user
        report.verified_at = timezone.now()
        report.save(update_fields=["status", "verified_by", "verified_at"])
        return Response(self.get_serializer(report).data)
    @extend_schema(
        request=None,
        responses={200: DiagnosticReportReadSerializer},
        summary="Release a verified diagnostic report",
        tags=["Diagnostics"],
    )
    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        report = self.get_object()
        self._require_verifier(report)
        if report.status != DiagnosticReport.Status.VERIFIED:
            raise ValidationError("A report must be verified before it can be released.")
        with transaction.atomic():
            report.status = DiagnosticReport.Status.RELEASED
            report.released_at = timezone.now()
            report.save(update_fields=["status", "released_at"])
            diagnostic_request = report.request
            diagnostic_request.status = DiagnosticRequest.Status.COMPLETED
            diagnostic_request.completed_at = timezone.now()
            diagnostic_request.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(self.get_serializer(report).data)
