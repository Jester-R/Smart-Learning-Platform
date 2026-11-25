from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("<int:pk>/", views.event_detail, name="detail"),
    path("new/", views.event_create, name="create"),
    path("<int:pk>/register/", views.event_register, name="register"),
    path("my/", views.my_registrations, name="my_registrations"),
]
