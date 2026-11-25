from django.urls import path

from . import views

app_name = "learning"

urlpatterns = [
    # Attendance
    path("attendance/", views.attendance, name="attendance"),
    path("attendance/record/", views.attendance_record, name="attendance_record"),
    path(
        "attendance/export/pdf/",
        views.attendance_export_pdf,
        name="attendance_export_pdf",
    ),

    # Teacher global video management
    path("teacher/videos/", views.teacher_video_manage, name="teacher_videos"),
    path("teacher/videos/new/", views.teacher_video_create, name="teacher_video_create"),

    # YouTube validation API
    path("api/youtube/validate/", views.youtube_validate_api, name="youtube_validate_api"),

    # Course lesson routes
    path("courses/<slug:slug>/lessons/new/", views.lesson_create, name="lesson_create"),
    path("courses/<slug:slug>/lessons/<int:pk>/", views.lesson_detail, name="lesson"),
    path("courses/<slug:slug>/lessons/<int:pk>/video/", views.lesson_video_file, name="video_file"),
    path(
        "courses/<slug:slug>/lessons/<int:pk>/edit/",
        views.lesson_update,
        name="lesson_edit",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:pk>/delete/",
        views.lesson_delete,
        name="lesson_delete",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:pk>/toggle-publish/",
        views.lesson_toggle_publish,
        name="lesson_toggle_publish",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:pk>/complete/",
        views.mark_complete,
        name="mark_complete",
    ),

    # Learning materials
    path(
        "courses/<slug:slug>/materials/new/",
        views.material_create,
        name="material_create",
    ),
    path(
        "courses/<slug:slug>/materials/<int:pk>/download/",
        views.material_download,
        name="material_download",
    ),
    path(
        "courses/<slug:slug>/materials/<int:pk>/delete/",
        views.material_delete,
        name="material_delete",
    ),
]
