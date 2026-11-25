from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("export/pdf/", views.notification_export_pdf, name="export_pdf"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
    path("<int:pk>/read-json/", views.mark_read_json, name="mark_read_json"),
    path("read-all/", views.mark_all_read, name="mark_all_read"),
    path("announcements/", views.announcement_list, name="announcements"),
    path(
        "announcements/new/",
        views.announcement_create,
        name="announcement_create",
    ),
]
