"""Compact PDF incident report generation."""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from beacon_call.models import Incident


def generate_incident_report(incident: Incident, output_path: Path) -> Path:
    """Write a one-page operational summary without embedding the camera image."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "BeaconTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=25,
        textColor=colors.HexColor("#17351B"),
        alignment=TA_LEFT,
        spaceAfter=12,
    )
    label = ParagraphStyle(
        "BeaconLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.HexColor("#4A594B"),
        leading=10,
    )
    body = ParagraphStyle(
        "BeaconBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#18201A"),
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"BeaconCall incident {incident.id}",
        author="BeaconCall",
    )
    people = str(incident.people_count) if incident.people_count is not None else "Pending"
    values = [
        ("INCIDENT", incident.id),
        ("STATUS", incident.status.replace("_", " ").upper()),
        ("DETECTED", incident.detected_at),
        ("CAMERA", incident.camera_name),
        ("LOCAL DETECTOR", f"{incident.detector_people_count} person candidate(s)"),
        ("OPENAI COUNT", people),
        ("CONFIDENCE", f"{incident.confidence_percent}%"),
        ("FRAME REGION", incident.frame_region),
    ]
    table = Table(
        [[Paragraph(escape(key), label), Paragraph(escape(value), body)] for key, value in values],
        colWidths=[1.35 * inch, 5.45 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E1D8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    scene = incident.scene_description or "Scene analysis was not available."
    outcome = incident.response or "Awaiting inbound acknowledgement."
    operator = incident.operator_name or "Not yet recorded"
    story = [
        Paragraph("BEACONCALL", label),
        Paragraph("Camera Incident Report", title),
        table,
        Spacer(1, 16),
        Paragraph("OPENAI SCENE DESCRIPTION", label),
        Spacer(1, 5),
        Paragraph(escape(scene), body),
        Spacer(1, 14),
        Paragraph("VOICE HANDOFF", label),
        Spacer(1, 5),
        Paragraph(f"Operator: {escape(operator)}<br/>Recorded response: {escape(outcome)}", body),
        Spacer(1, 16),
        Paragraph(
            "This automated report describes visible camera content only. It does not identify "
            "people, diagnose injury or distress, contact emergency services, or replace human "
            "review.",
            ParagraphStyle(
                "BeaconDisclaimer",
                parent=body,
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#5B655C"),
            ),
        ),
    ]
    doc.build(story)
    return output_path
