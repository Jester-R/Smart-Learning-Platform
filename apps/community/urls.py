from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("", views.forum_list, name="forum_list"),
    path("posts/new/", views.post_create, name="post_create"),
    path("posts/<int:pk>/", views.post_detail, name="post_detail"),
    path("posts/<int:pk>/comments/", views.comment_create, name="comment_create"),
    path("posts/<int:pk>/like/", views.toggle_like, name="toggle_like"),
    path("posts/<int:pk>/save/", views.toggle_save, name="toggle_save"),
    path("posts/<int:pk>/report/", views.report_post, name="report_post"),
    path("moderation/", views.moderation_list, name="moderation"),
    path("moderation/<int:pk>/", views.moderate_post, name="moderate_post"),
]
