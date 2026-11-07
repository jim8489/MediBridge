from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone

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


def safe_text(value):
    if value is None or value == "":
        return "—"

    return escape(str(value)).replace("\n", "<br/>")


def generate_prescription_pdf(prescription):

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Prescription {prescription.prescription_number}",
        author="MediBridge",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "PrescriptionTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=5,
    )

    subtitle_style = ParagraphStyle(
        "PrescriptionSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey,
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "PrescriptionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#17365D"),
        spaceBefore=13,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "PrescriptionBody",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=12,
    )

    label_style = ParagraphStyle(
        "PrescriptionLabel",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    story = []

    patient = prescription.patient
    doctor = prescription.doctor

    patient_user = patient.user
    doctor_user = doctor.user

    patient_name = patient_user.get_full_name() or patient_user.email
    doctor_name = doctor_user.get_full_name() or doctor_user.email

    issued_at = (
        timezone.localtime(prescription.issued_at).strftime(
            "%d %b %Y, %I:%M %p"
        )
        if prescription.issued_at
        else "Not issued"
    )

    valid_until = (
        prescription.valid_until.strftime("%d %b %Y")
        if prescription.valid_until
        else "Not specified"
    )

    # Header
    story.append(Paragraph("MediBridge", title_style))
    story.append(
        Paragraph("MEDICAL PRESCRIPTION", subtitle_style)
    )

    # Patient and doctor information
    story.append(
        Paragraph("Prescription Information", heading_style)
    )

    information = [
        ("Prescription Number", prescription.prescription_number),
        ("Patient Name", patient_name),
        ("Patient Number", patient.patient_number),
        ("Doctor", doctor_name),
        ("Doctor Email", doctor_user.email),
        ("Issued At", issued_at),
        ("Valid Until", valid_until),
        ("Prescription Status", prescription.status),
    ]

    information_table = Table(
        [
            [
                Paragraph(safe_text(label), label_style),
                Paragraph(safe_text(value), body_style),
            ]
            for label, value in information
        ],
        colWidths=[48 * mm, 119 * mm],
    )

    information_table.setStyle(
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

    story.append(information_table)

    # Medication details
    story.append(
        Paragraph("Prescribed Medication", heading_style)
    )

    medication_rows = [
        [
            Paragraph("Medication", label_style),
            Paragraph("Dosage / Route", label_style),
            Paragraph("Frequency / Duration", label_style),
            Paragraph("Quantity / Instructions", label_style),
        ]
    ]

    for item in prescription.items.all():

        medication_details = (
            f"<b>{safe_text(item.medication_name)}</b>"
        )

        if item.generic_name:
            medication_details += (
                f"<br/>Generic: {safe_text(item.generic_name)}"
            )

        if item.strength:
            medication_details += (
                f"<br/>Strength: {safe_text(item.strength)}"
            )

        dosage_details = safe_text(item.dosage)

        if item.route:
            dosage_details += (
                f"<br/>Route: {safe_text(item.route)}"
            )

        schedule_details = (
            f"{safe_text(item.frequency)}"
            f"<br/>Duration: {safe_text(item.duration)}"
        )

        quantity_details = safe_text(item.quantity)

        if item.instructions:
            quantity_details += (
                f"<br/>{safe_text(item.instructions)}"
            )

        medication_rows.append([
            Paragraph(medication_details, body_style),
            Paragraph(dosage_details, body_style),
            Paragraph(schedule_details, body_style),
            Paragraph(quantity_details, body_style),
        ])

    medication_table = Table(
        medication_rows,
        colWidths=[48 * mm, 36 * mm, 42 * mm, 41 * mm],
        repeatRows=1,
    )

    medication_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#EAF0F6"),
            ),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )

    story.append(medication_table)

    # General instructions
    story.append(
        Paragraph("General Instructions", heading_style)
    )

    story.append(
        Paragraph(
            safe_text(
                prescription.general_instructions
                or "No additional instructions recorded."
            ),
            body_style,
        )
    )

    # Disclaimer
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "This prescription was electronically issued through "
            "MediBridge. Follow the instructions of the issuing "
            "doctor and contact the doctor if clarification is needed.",
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
