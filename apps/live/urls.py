from django.urls import path

from . import views

app_name = "live"

urlpatterns = [
    path("", views.live_portal, name="portal"),
    path("sessions/new/", views.session_create, name="create"),
    path("sessions/<int:pk>/", views.session_detail, name="detail"),
]
