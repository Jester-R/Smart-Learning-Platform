from html import escape
from io import BytesIO
from pathlib import Path

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_payment_pdf(payment, document_type):
    buffer = BytesIO()
    filename = f"smart-learning-{document_type}-{payment.pk}.pdf"
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Smart Learning Platform {document_type.title()}",
        author="Smart Learning Platform",
    )

    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    for font_path in (
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("SLPPaymentFont", str(font_path)))
            font_name = font_bold = "SLPPaymentFont"
            break

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PaymentTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#24283b"),
        alignment=TA_LEFT,
        fontSize=20,
        leading=24,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "PaymentMeta",
        parent=styles["Normal"],
        textColor=colors.HexColor("#565f89"),
        fontSize=9,
        leading=12,
    )
    cell_style = ParagraphStyle(
        "PaymentCell",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#24283b"),
    )
    label_style = ParagraphStyle(
        "PaymentLabel",
        parent=cell_style,
        fontName=font_bold,
        textColor=colors.HexColor("#3d59a1"),
    )

    invoice = getattr(payment, "invoice", None)
    number = invoice.number if invoice else f"PAY-{payment.pk:06d}"
    issued_at = invoice.issued_at if invoice else payment.created_at
    description = (
        f"{payment.course.code} - {payment.course.title}"
        if payment.course_id
        else (payment.plan.name if payment.plan_id else "Smart Learning Platform")
    )
    method = payment.method.name if payment.method_id else "-"
    rows = [
        (Paragraph("Document no.", label_style), Paragraph(escape(number), cell_style)),
        (
            Paragraph("Issued", label_style),
            Paragraph(issued_at.strftime("%b %d, %Y %H:%M"), cell_style),
        ),
        (
            Paragraph("Billed to", label_style),
            Paragraph(escape(payment.student.full_name), cell_style),
        ),
        (
            Paragraph("Email", label_style),
            Paragraph(escape(payment.student.email), cell_style),
        ),
        (
            Paragraph("Item", label_style),
            Paragraph(escape(description), cell_style),
        ),
        (
            Paragraph("Payment method", label_style),
            Paragraph(escape(method), cell_style),
        ),
        (
            Paragraph("Reference", label_style),
            Paragraph(escape(payment.reference or "-"), cell_style),
        ),
        (
            Paragraph("Status", label_style),
            Paragraph(payment.get_status_display(), cell_style),
        ),
        (
            Paragraph("Amount", label_style),
            Paragraph(f"{payment.amount:,.2f}", cell_style),
        ),
    ]
    table = Table(rows, colWidths=[40 * mm, 130 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#eef1fa")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7cce0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story = [
        Paragraph("Smart Learning Platform", title_style),
        Paragraph(f"{document_type.title()} · {number}", meta_style),
        Spacer(1, 8 * mm),
        table,
        Spacer(1, 10 * mm),
        Paragraph(
            "Thank you for learning with Smart Learning Platform.", meta_style
        ),
    ]
    doc.build(story)
    response.content = buffer.getvalue()
    return response
