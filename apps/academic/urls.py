from django.urls import path

from . import views

app_name = "academic"

urlpatterns = [
    path("timetable/", views.timetable, name="timetable"),
    path("calendar/", views.academic_calendar, name="calendar"),
    path("exam-schedule/", views.exam_schedule, name="exam_schedule"),
    path("timetable/new/", views.schedule_create, name="schedule_create"),
    path("calendar/new/", views.calendar_event_create, name="calendar_event_create"),
    path(
        "exam-schedule/new/",
        views.exam_schedule_create,
        name="exam_schedule_create",
    ),
]
