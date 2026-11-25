from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.analytics.models import ActivityLog

from .forms import EventForm
from .models import Event, EventRegistration


def _require_permission(user, code):
    if not user.is_authenticated or not user.has_permission(code):
        raise PermissionDenied("You do not have permission for this action.")


def _can_register(user, event):
    if not user.is_authenticated or not user.has_permission("event.register"):
        return False
    if event.is_exclusive and not user.has_permission("workshop.exclusive"):
        return False
    if event.is_full:
        return False
    return not EventRegistration.objects.filter(event=event, user=user, status="registered").exists()


def event_list(request):
    events = Event.objects.filter(is_published=True).select_related("category", "university")
    return render(request, "events/list.html", {"events": events})


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk, is_published=True)
    registered = (
        request.user.is_authenticated
        and EventRegistration.objects.filter(
            event=event, user=request.user, status="registered"
        ).exists()
    )
    return render(
        request,
        "events/detail.html",
        {"event": event, "registered": registered, "can_register": _can_register(request.user, event)},
    )


@login_required
def event_create(request):
    _require_permission(request.user, "event.manage")
    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.created_by = request.user
        event.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="Event",
            object_id=event.pk,
            description=f"Created event {event.title}",
        )
        messages.success(request, "Event created.")
        return redirect("events:detail", pk=event.pk)
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Create event", "cancel_url": "events:list"},
    )


@login_required
def event_register(request, pk):
    _require_permission(request.user, "event.register")
    event = get_object_or_404(Event, pk=pk, is_published=True)
    if event.is_exclusive and not request.user.has_permission("workshop.exclusive"):
        raise PermissionDenied("This workshop is reserved for Premium members.")
    if event.is_full:
        raise PermissionDenied("This event is full.")
    if request.method == "POST":
        registration, created = EventRegistration.objects.get_or_create(
            event=event, user=request.user, defaults={"status": "registered"}
        )
        if created:
            ActivityLog.objects.create(
                user=request.user,
                action=ActivityLog.Action.CREATE,
                model_name="EventRegistration",
                object_id=registration.pk,
                description=f"Registered for event {event.title}",
            )
            messages.success(request, "Registration confirmed.")
        else:
            messages.info(request, "You are already registered.")
        return redirect("events:detail", pk=event.pk)
    return render(request, "events/register.html", {"event": event})


@login_required
def my_registrations(request):
    registrations = EventRegistration.objects.filter(user=request.user).select_related("event")
    return render(request, "events/my_registrations.html", {"registrations": registrations})
