from django.urls import path

from . import views

app_name = "scholarships"

urlpatterns = [
    path("", views.scholarship_list, name="list"),
    path("<int:pk>/", views.scholarship_detail, name="detail"),
    path("new/", views.scholarship_create, name="create"),
    path("<int:pk>/apply/", views.scholarship_apply, name="apply"),
    path("applications/", views.my_applications, name="my_applications"),
]
