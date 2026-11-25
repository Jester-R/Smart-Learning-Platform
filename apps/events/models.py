from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import University


class EventCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "event categories"

    def __str__(self) -> str:
        return self.name


class Event(models.Model):
    category = models.ForeignKey(
        EventCategory, on_delete=models.SET_NULL, related_name="events", null=True, blank=True
    )
    university = models.ForeignKey(
        University, on_delete=models.SET_NULL, related_name="events", null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_events", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    is_exclusive = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]

    def clean(self):
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError("End time must be after start time.")

    @property
    def is_full(self) -> bool:
        return bool(self.capacity) and self.registrations.filter(status="registered").count() >= self.capacity

    def __str__(self) -> str:
        return self.title


class EventRegistration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        ATTENDED = "attended", "Attended"
        CANCELLED = "cancelled", "Cancelled"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="events_unique_registration")
        ]

    def __str__(self) -> str:
        return f"{self.user.full_name} - {self.event.title}"
