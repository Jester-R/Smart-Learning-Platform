from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.analytics.models import ActivityLog

from .forms import FAQForm, FeedbackForm, SupportTicketForm, TicketMessageForm
from .models import FAQ, SupportTicket


def _require_permission(user, code):
    if not user.is_authenticated or not user.has_permission(code):
        raise PermissionDenied("You do not have permission for this action.")


def _can_manage_tickets(user):
    return user.is_authenticated and user.has_permission("ticket.manage")


def faq_list(request):
    return render(request, "support/faq_list.html", {"faqs": FAQ.objects.filter(is_published=True)})


@login_required
def faq_manage(request):
    _require_permission(request.user, "faq.manage")
    form = FAQForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "FAQ saved.")
        return redirect("support:faq_manage")
    return render(request, "support/faq_manage.html", {"form": form, "faqs": FAQ.objects.all()})


@login_required
def ticket_create(request):
    _require_permission(request.user, "ticket.create")
    form = SupportTicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.user = request.user
        ticket.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="SupportTicket",
            object_id=ticket.pk,
            description=f"Created support ticket {ticket.subject}",
        )
        messages.success(request, "Support ticket created.")
        return redirect("support:ticket_detail", pk=ticket.pk)
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Create support ticket", "cancel_url": "support:faq_list"},
    )


@login_required
def ticket_list(request):
    _require_permission(request.user, "ticket.view_own")
    tickets = (
        SupportTicket.objects.all()
        if _can_manage_tickets(request.user)
        else SupportTicket.objects.filter(user=request.user)
    )
    return render(request, "support/ticket_list.html", {"tickets": tickets})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk)
    can_manage = _can_manage_tickets(request.user)
    if ticket.user_id != request.user.pk and not can_manage:
        raise PermissionDenied("You cannot view this ticket.")
    form = TicketMessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.ticket = ticket
        message.author = request.user
        message.is_staff_reply = can_manage
        message.save()
        if can_manage:
            ticket.status = request.POST.get("status", ticket.status)
            ticket.save()
        messages.success(request, "Reply added.")
        return redirect("support:ticket_detail", pk=ticket.pk)
    return render(
        request,
        "support/ticket_detail.html",
        {
            "ticket": ticket,
            "form": form,
            "can_manage": can_manage,
            "statuses": SupportTicket.Status.choices,
            "ticket_messages": ticket.messages.all(),
        },
    )


@login_required
def feedback_create(request):
    _require_permission(request.user, "ticket.create")
    form = FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        feedback = form.save(commit=False)
        feedback.user = request.user
        feedback.save()
        messages.success(request, "Thank you for your feedback.")
        return redirect("support:feedback_create")
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Send feedback", "cancel_url": "support:faq_list"},
    )
