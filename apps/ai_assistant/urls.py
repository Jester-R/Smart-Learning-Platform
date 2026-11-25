from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("new/", views.new_conversation, name="new"),
    path("history/clear/", views.clear_history, name="clear_history"),
    path("send/", views.send_message, name="send"),
]
