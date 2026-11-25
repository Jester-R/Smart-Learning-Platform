from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import is_admin, is_teacher, role_required
from apps.courses.models import Enrollment

from .forms import AnnouncementForm
from .models import Announcement, Notification
from .services import notify_many


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    return render(
        request, "notifications/list.html", {"notifications": notifications}
    )


def notification_report_queryset(user):
    """Return ``(queryset, show_all)`` for the notification PDF report.

    Administrators see every notification in the platform; other users only see
    notifications addressed to them.
    """
    queryset = Notification.objects.select_related("recipient")
    if is_admin(user):
        return queryset, True
    return queryset.filter(recipient=user), False


@login_required
def notification_export_pdf(request):
    """Download a PDF report of notifications.

    Administrators receive a platform-wide report; other users receive a report
    containing only their own notifications.
    """
    from html import escape
    from io import BytesIO
    from pathlib import Path

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    notifications_query, show_all = notification_report_queryset(request.user)
    notifications = list(notifications_query.order_by("-created_at"))

    total = len(notifications)
    unread = sum(1 for notification in notifications if not notification.is_read)
    report_title = "Notification report"
    scope_label = (
        "All platform notifications"
        if show_all
        else f"Notifications for {request.user.full_name}"
    )

    buffer = BytesIO()
    response = HttpResponse(content_type="application/pdf")
    filename_scope = "all-notifications" if show_all else "my-notifications"
    response["Content-Disposition"] = (
        f'attachment; filename="smart-learning-{filename_scope}-'
        f'{timezone.localtime():%Y%m%d}.pdf"'
    )
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title="Smart Learning Platform Notification Report",
        author="Smart Learning Platform",
    )

    styles = getSampleStyleSheet()
    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    for font_path in (
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("SLPNotificationFont", str(font_path)))
            font_name = font_bold = "SLPNotificationFont"
            break

    title_style = ParagraphStyle(
        "NotificationReportTitle",
        parent=styles["Title"],
        fontName=font_bold,
        textColor=colors.HexColor("#24283b"),
        alignment=TA_LEFT,
        fontSize=18,
        leading=22,
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "NotificationReportMeta",
        parent=styles["Normal"],
        fontName=font_name,
        textColor=colors.HexColor("#565f89"),
        fontSize=9,
        leading=12,
    )
    cell_style = ParagraphStyle(
        "NotificationReportCell",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#24283b"),
    )
    header_style = ParagraphStyle(
        "NotificationReportHeader",
        parent=cell_style,
        fontName=font_bold,
        textColor=colors.white,
    )

    if show_all:
        headers = ("Date", "Recipient", "Type", "Status", "Title", "Message")
        widths = [26 * mm, 40 * mm, 30 * mm, 18 * mm, 55 * mm, 96 * mm]
        data = [[Paragraph(label, header_style) for label in headers]]
        for notification in notifications:
            data.append(
                [
                    Paragraph(
                        timezone.localtime(notification.created_at).strftime(
                            "%b %d, %Y %H:%M"
                        ),
                        cell_style,
                    ),
                    Paragraph(escape(notification.recipient.full_name), cell_style),
                    Paragraph(escape(notification.get_kind_display()), cell_style),
                    Paragraph(
                        "Read" if notification.is_read else "Unread", cell_style
                    ),
                    Paragraph(escape(notification.title), cell_style),
                    Paragraph(
                        escape(notification.message).replace("\n", "<br/>"),
                        cell_style,
                    ),
                ]
            )
    else:
        headers = ("Date", "Type", "Status", "Title", "Message")
        widths = [28 * mm, 32 * mm, 20 * mm, 60 * mm, 125 * mm]
        data = [[Paragraph(label, header_style) for label in headers]]
        for notification in notifications:
            data.append(
                [
                    Paragraph(
                        timezone.localtime(notification.created_at).strftime(
                            "%b %d, %Y %H:%M"
                        ),
                        cell_style,
                    ),
                    Paragraph(escape(notification.get_kind_display()), cell_style),
                    Paragraph(
                        "Read" if notification.is_read else "Unread", cell_style
                    ),
                    Paragraph(escape(notification.title), cell_style),
                    Paragraph(
                        escape(notification.message).replace("\n", "<br/>"),
                        cell_style,
                    ),
                ]
            )

    story = [
        Paragraph("Smart Learning Platform", title_style),
        Paragraph(
            f"{report_title} · {scope_label}<br/>"
            f"Generated {timezone.localtime():%b %d, %Y %H:%M} · "
            f"Total {total} · Unread {unread} · Read {total - unread}",
            small_style,
        ),
        Spacer(1, 8 * mm),
    ]

    if total:
        table = Table(data, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3d59a1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#eef1fa")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7cce0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
    else:
        story.append(
            Paragraph("No notifications have been recorded yet.", small_style)
        )

    doc.build(story)
    response.content = buffer.getvalue()
    return response


@login_required
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    if notification.link:
        return redirect(notification.link)
    return redirect("notifications:list")


@login_required
def mark_all_read(request):
    if request.method == "POST":
        request.user.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
    return redirect("notifications:list")


@login_required
def mark_read_json(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    return JsonResponse({"ok": True})


@login_required
def announcement_list(request):
    announcements = (
        Announcement.objects.filter(is_published=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
        .select_related("course", "created_by")
    )
    if is_teacher(request.user) and not is_admin(request.user):
        announcements = announcements.filter(
            Q(audience__in=[Announcement.Audience.EVERYONE, Announcement.Audience.TEACHERS])
            | Q(course__teacher=request.user)
        )
    elif not is_admin(request.user):
        announcements = announcements.filter(
            Q(audience__in=[Announcement.Audience.EVERYONE, Announcement.Audience.STUDENTS])
            | Q(
                audience=Announcement.Audience.COURSE,
                course__enrollments__student=request.user,
            )
        )
    return render(
        request,
        "notifications/announcements.html",
        {"announcements": announcements.distinct()},
    )


@role_required("teacher", "admin")
def announcement_create(request):
    form = AnnouncementForm(
        request.POST or None, user=request.user, initial={"is_published": True}
    )
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        if announcement.is_published and not announcement.published_at:
            announcement.publish()
        if announcement.is_published:
            recipients = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
            if announcement.audience == Announcement.Audience.STUDENTS:
                recipients = recipients.filter(role=User.Role.STUDENT)
            elif announcement.audience == Announcement.Audience.TEACHERS:
                recipients = recipients.filter(role=User.Role.TEACHER)
            elif announcement.audience == Announcement.Audience.COURSE:
                student_ids = Enrollment.objects.filter(
                    course=announcement.course
                ).values_list("student_id", flat=True)
                recipients = recipients.filter(pk__in=student_ids)
            notify_many(
                recipients,
                f"Announcement: {announcement.title}",
                announcement.content[:500],
                kind=Notification.Kind.ANNOUNCEMENT,
                link="/notifications/announcements/",
            )
        messages.success(request, "Announcement published.")
        return redirect("notifications:announcements")
    return render(
        request,
        "notifications/announcement_form.html",
        {"form": form},
    )
