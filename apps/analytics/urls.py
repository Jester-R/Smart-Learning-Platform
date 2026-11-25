from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("reports/", views.reports, name="reports"),
    path("activity/", views.activity_log, name="activity"),
]
