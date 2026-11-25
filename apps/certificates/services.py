import math
from decimal import Decimal
from io import BytesIO
from textwrap import wrap

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.assessments.models import ExamAttempt, QuizAttempt, Submission
from apps.courses.models import Enrollment
from apps.learning.models import LearningProgress

from .models import Certificate, CertificateTemplate


def check_eligibility(student, course) -> dict:
    reasons = []
    enrollment = Enrollment.objects.filter(student=student, course=course).first()
    if enrollment is None:
        return {
            "eligible": False,
            "reasons": ["You are not enrolled in this course."],
            "stats": {},
        }
    if not course.certificate_enabled:
        reasons.append("Certificates are not enabled for this course.")

    lessons = course.lessons.filter(is_published=True)
    total_lessons = lessons.count()
    completed_lessons = LearningProgress.objects.filter(
        student=student,
        lesson__course=course,
        lesson__is_published=True,
        is_completed=True,
    ).count()
    lesson_percent = (
        (completed_lessons / total_lessons * 100) if total_lessons else 100
    )
    if lesson_percent < course.min_lesson_completion:
        reasons.append(
            f"Complete at least {course.min_lesson_completion}% of lessons "
            f"(currently {lesson_percent:.1f}%)."
        )

    assignments = course.assignments.filter(is_published=True)
    total_assignments = assignments.count()
    submitted_assignments = (
        Submission.objects.filter(
            student=student,
            assignment__in=assignments,
            status__in=[Submission.Status.GRADED, Submission.Status.RETURNED],
        )
        .values("assignment")
        .distinct()
        .count()
    )
    assignment_percent = (
        (submitted_assignments / total_assignments * 100)
        if total_assignments
        else 100
    )
    if assignment_percent < course.min_assignment_completion:
        reasons.append(
            f"Complete at least {course.min_assignment_completion}% of assignments "
            f"(currently {assignment_percent:.1f}%)."
        )

    quiz_scores = []
    quiz_attempts = QuizAttempt.objects.filter(
        student=student,
        quiz__course=course,
        status__in=[QuizAttempt.Status.GRADED, QuizAttempt.Status.SUBMITTED],
        max_score__gt=0,
    )
    for attempt in quiz_attempts:
        quiz_scores.append(float(attempt.score / attempt.max_score * 100))
    quiz_average = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 100
    if quiz_average < course.min_quiz_average:
        reasons.append(
            f"Reach a quiz average of {course.min_quiz_average}% "
            f"(currently {quiz_average:.1f}%)."
        )

    exam_scores = []
    exam_attempts = ExamAttempt.objects.filter(
        student=student,
        exam__course=course,
        status__in=[ExamAttempt.Status.GRADED, ExamAttempt.Status.SUBMITTED],
        max_score__gt=0,
    )
    for attempt in exam_attempts:
        exam_scores.append(float(attempt.score / attempt.max_score * 100))
    exam_average = sum(exam_scores) / len(exam_scores) if exam_scores else 100
    if exam_scores and exam_average < course.passing_score:
        reasons.append(
            f"Reach an examination average of {course.passing_score}% "
            f"(currently {exam_average:.1f}%)."
        )

    return {
        "eligible": not reasons,
        "reasons": reasons,
        "stats": {
            "lesson_percent": round(lesson_percent, 1),
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "assignment_percent": round(assignment_percent, 1),
            "submitted_assignments": submitted_assignments,
            "total_assignments": total_assignments,
            "quiz_average": round(quiz_average, 1),
            "exam_average": round(exam_average, 1),
            "enrollment_status": enrollment.status,
        },
    }


def _draw_arc_text(
    pdf, text, center_x, center_y, radius, start_angle, end_angle, font_size, color
):
    from reportlab.lib import colors

    pdf.setFillColor(colors.HexColor(color))
    pdf.setFont("Helvetica-Bold", font_size)
    step = max(len(text) - 1, 1)
    rotation_offset = -90 if end_angle < start_angle else -270
    for index, character in enumerate(text):
        angle = start_angle + (end_angle - start_angle) * index / step
        radians = math.radians(angle)
        pdf.saveState()
        pdf.translate(
            center_x + radius * math.cos(radians),
            center_y + radius * math.sin(radians),
        )
        pdf.rotate(angle + rotation_offset)
        pdf.drawCentredString(0, 0, character)
        pdf.restoreState()


def _draw_seal(pdf, center_x, center_y, radius, year):
    from reportlab.lib import colors

    gold = colors.HexColor("#c8971b")
    deep_gold = colors.HexColor("#8a6209")
    pale_gold = colors.HexColor("#f7df9a")
    parchment = colors.HexColor("#fffdf5")
    pdf.saveState()

    pdf.setFillColor(parchment)
    pdf.setStrokeColor(deep_gold)
    pdf.setLineWidth(2.4)
    pdf.circle(center_x, center_y, radius * 0.98, stroke=1, fill=1)

    for index in range(28):
        angle = index * (360 / 28)
        half_width = 3.2 if index % 2 == 0 else 2.1
        inner = radius * 0.3
        outer = radius * (0.73 if index % 2 == 0 else 0.65)
        left = math.radians(angle - half_width)
        right = math.radians(angle + half_width)
        tip = math.radians(angle)
        path = pdf.beginPath()
        path.moveTo(
            center_x + inner * math.cos(left),
            center_y + inner * math.sin(left),
        )
        path.lineTo(
            center_x + outer * math.cos(tip),
            center_y + outer * math.sin(tip),
        )
        path.lineTo(
            center_x + inner * math.cos(right),
            center_y + inner * math.sin(right),
        )
        path.close()
        pdf.setFillColor(pale_gold if index % 2 == 0 else gold)
        pdf.drawPath(path, stroke=0, fill=1)

    pdf.setFillColor(parchment)
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(1)
    pdf.circle(center_x, center_y, radius * 0.58, stroke=1, fill=1)
    pdf.setStrokeColor(deep_gold)
    pdf.setLineWidth(0.8)
    pdf.circle(center_x, center_y, radius * 0.78, stroke=1, fill=0)

    for side in (-1, 1):
        stem = pdf.beginPath()
        for index in range(41):
            progress = index / 40
            angle = math.radians(
                (235 - 130 * progress) if side < 0 else (305 + 130 * progress)
            )
            leaf_x = center_x + radius * 0.43 * math.cos(angle)
            leaf_y = center_y + radius * 0.43 * math.sin(angle)
            if index == 0:
                stem.moveTo(leaf_x, leaf_y)
            else:
                stem.lineTo(leaf_x, leaf_y)
        pdf.setStrokeColor(deep_gold)
        pdf.setLineWidth(1.1)
        pdf.drawPath(stem, stroke=1, fill=0)

        for index in range(10):
            angle = (232 - 13.5 * index) if side < 0 else (308 + 13.5 * index)
            radians = math.radians(angle)
            pdf.saveState()
            pdf.translate(
                center_x + radius * 0.43 * math.cos(radians),
                center_y + radius * 0.43 * math.sin(radians),
            )
            pdf.rotate(angle + 90)
            pdf.setFillColor(gold if index % 2 == 0 else pale_gold)
            pdf.setStrokeColor(deep_gold)
            pdf.setLineWidth(0.4)
            pdf.ellipse(
                -radius * 0.1, -radius * 0.035,
                radius * 0.1, radius * 0.035,
                stroke=1, fill=1,
            )
            pdf.restoreState()

    star = []
    for index in range(10):
        angle = math.radians(90 + index * 36)
        distance = radius * (0.18 if index % 2 == 0 else 0.075)
        star.append(
            (
                center_x + distance * math.cos(angle),
                center_y + radius * 0.12 + distance * math.sin(angle),
            )
        )
    pdf.setFillColor(deep_gold)
    path = pdf.beginPath()
    path.moveTo(*star[0])
    for point in star[1:]:
        path.lineTo(*point)
    path.close()
    pdf.drawPath(path, stroke=0, fill=1)

    pdf.setFillColor(gold)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawCentredString(center_x, center_y - radius * 0.09, str(year))

    banner_width = radius * 0.92
    banner_height = radius * 0.2
    banner_top = center_y - radius * 0.18
    banner_bottom = banner_top - banner_height
    banner = pdf.beginPath()
    banner.moveTo(center_x - banner_width / 2, banner_top)
    banner.lineTo(center_x + banner_width / 2, banner_top)
    banner.lineTo(
        center_x + banner_width / 2 + radius * 0.06,
        (banner_top + banner_bottom) / 2,
    )
    banner.lineTo(center_x + banner_width / 2, banner_bottom)
    banner.lineTo(center_x - banner_width / 2, banner_bottom)
    banner.lineTo(
        center_x - banner_width / 2 - radius * 0.06,
        (banner_top + banner_bottom) / 2,
    )
    banner.close()
    pdf.setFillColor(deep_gold)
    pdf.drawPath(banner, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawCentredString(
        center_x, banner_bottom + banner_height * 0.3, "EXCELLENCE"
    )

    _draw_arc_text(
        pdf, "OFFICIAL SEAL", center_x, center_y, radius * 0.87,
        155, 25, 7.8, "#8a6209",
    )
    _draw_arc_text(
        pdf, "SMART LEARNING", center_x, center_y, radius * 0.87,
        205, 335, 7.8, "#8a6209",
    )
    pdf.restoreState()


def _render_pdf(certificate) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    pdf.setTitle(f"Certificate {certificate.certificate_id}")

    template = certificate.template
    if template and template.background_image:
        try:
            pdf.drawImage(
                template.background_image.path,
                0,
                0,
                width=page_width,
                height=page_height,
                preserveAspectRatio=False,
                mask="auto",
            )
        except Exception:
            pass

    pdf.setStrokeColor(colors.HexColor("#1d4ed8"))
    pdf.setLineWidth(4)
    pdf.rect(18 * mm, 18 * mm, page_width - 36 * mm, page_height - 36 * mm)

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont("Helvetica-Bold", 34)
    pdf.drawCentredString(page_width / 2, page_height - 55 * mm, "Certificate of Completion")

    pdf.setFont("Helvetica", 14)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawCentredString(page_width / 2, page_height - 72 * mm, "This certifies that")

    pdf.setFont("Helvetica-Bold", 28)
    pdf.setFillColor(colors.HexColor("#1d4ed8"))
    pdf.drawCentredString(page_width / 2, page_height - 92 * mm, certificate.student.full_name)

    pdf.setFont("Helvetica", 14)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawCentredString(page_width / 2, page_height - 110 * mm, "has successfully completed")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawCentredString(page_width / 2, page_height - 125 * mm, certificate.course.title)

    body = (
        template.body_text
        if template
        else "Issued by the Smart Learning Platform in recognition of course completion."
    )
    body = body.format(
        student_name=certificate.student.full_name,
        course_title=certificate.course.title,
        issue_date=certificate.issued_at.strftime("%B %d, %Y"),
    )
    pdf.setFont("Helvetica", 10)
    text = pdf.beginText(40 * mm, page_height - 145 * mm)
    for line in wrap(body, 100):
        text.textLine(line)
    pdf.drawText(text)

    verification_url = settings.SITE_URL.rstrip("/") + reverse(
        "certificates:verify", args=[certificate.verification_code]
    )
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawString(25 * mm, 30 * mm, f"Certificate ID: {certificate.certificate_id}")
    pdf.drawString(25 * mm, 25 * mm, f"Issued: {certificate.issued_at:%B %d, %Y}")
    pdf.drawString(25 * mm, 20 * mm, f"Verify: {verification_url}")

    issuer = template.issuer_name if template else "Smart Learning Platform"
    pdf.drawRightString(
        page_width - 25 * mm,
        30 * mm,
        f"Issued by: {certificate.issued_by.full_name if certificate.issued_by else issuer}",
    )

    _draw_seal(pdf, page_width - 64 * mm, 75 * mm, 27 * mm, certificate.issued_at.year)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def ensure_certificate_pdf(certificate):
    """Generate and persist the certificate PDF when it is missing."""
    if certificate.pdf_file:
        return certificate
    pdf_bytes = _render_pdf(certificate)
    certificate.pdf_file.save(
        f"{certificate.certificate_id}.pdf",
        ContentFile(pdf_bytes),
        save=True,
    )
    return certificate


def issue_certificate(student, course, issued_by=None):
    existing = Certificate.objects.filter(student=student, course=course).first()
    if existing:
        return existing, False

    eligibility = check_eligibility(student, course)
    if not eligibility["eligible"]:
        raise ValidationError(" ".join(eligibility["reasons"]))

    enrollment = Enrollment.objects.filter(student=student, course=course).first()
    template = (
        CertificateTemplate.objects.filter(is_default=True).first()
        or CertificateTemplate.objects.first()
    )
    certificate = Certificate.objects.create(
        student=student,
        course=course,
        template=template,
        issued_by=issued_by,
        grade_at_issue=enrollment.final_grade if enrollment else None,
    )
    ensure_certificate_pdf(certificate)
    return certificate, True
