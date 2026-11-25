from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("", views.faq_list, name="faq_list"),
    path("faq/new/", views.faq_manage, name="faq_manage"),
    path("tickets/new/", views.ticket_create, name="ticket_create"),
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("feedback/", views.feedback_create, name="feedback_create"),
]
