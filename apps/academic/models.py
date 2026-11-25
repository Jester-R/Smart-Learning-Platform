from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import University


class ClassSchedule(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="class_schedules"
    )
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="lectured_schedules",
        null=True,
        blank=True,
    )
    university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        related_name="class_schedules",
        null=True,
        blank=True,
    )
    day_of_week = models.PositiveSmallIntegerField(
        choices=Weekday.choices, db_index=True
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_week", "start_time", "course__code"]
        verbose_name = "class schedule"
        verbose_name_plural = "class schedules"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "day_of_week", "start_time"],
                name="academic_class_schedule_unique",
            )
        ]

    def clean(self):
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")

    def __str__(self) -> str:
        return f"{self.course.code} - {self.get_day_of_week_display()} {self.start_time}"


class ClassSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    schedule = models.ForeignKey(
        ClassSchedule, on_delete=models.CASCADE, related_name="sessions"
    )
    date = models.DateField(db_index=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_at"]
        verbose_name = "class session"
        verbose_name_plural = "class sessions"
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "date", "start_at"],
                name="academic_class_session_unique",
            )
        ]

    def clean(self):
        if self.end_at and self.start_at and self.end_at <= self.start_at:
            raise ValidationError("End time must be after start time.")

    def __str__(self) -> str:
        return f"{self.schedule.course.code} - {self.date:%Y-%m-%d}"


class AcademicCalendar(models.Model):
    class EventType(models.TextChoices):
        HOLIDAY = "holiday", "Holiday"
        EXAM = "exam", "Exam period"
        REGISTRATION = "registration", "Registration"
        DEADLINE = "deadline", "Deadline"
        WORKSHOP = "workshop", "Workshop"
        OTHER = "other", "Other"

    university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "title"]
        verbose_name = "academic calendar event"
        verbose_name_plural = "academic calendar events"

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    def __str__(self) -> str:
        return self.title


class ExamSchedule(models.Model):
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="exam_schedules"
    )
    exam = models.ForeignKey(
        "assessments.Exam",
        on_delete=models.SET_NULL,
        related_name="scheduled_slots",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    venue = models.CharField(max_length=120, blank=True)
    is_published = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "course__code"]
        verbose_name = "exam schedule"
        verbose_name_plural = "exam schedules"

    def clean(self):
        if self.end_at and self.start_at and self.end_at <= self.start_at:
            raise ValidationError("End time must be after start time.")

    def __str__(self) -> str:
        return f"{self.course.code} - {self.title} - {self.start_at:%Y-%m-%d %H:%M}"
