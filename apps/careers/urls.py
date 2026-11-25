from django.urls import path

from . import views

app_name = "careers"

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("<int:pk>/", views.job_detail, name="job_detail"),
    path("companies/profile/", views.company_profile, name="company_profile"),
    path("companies/jobs/", views.company_jobs, name="company_jobs"),
    path("jobs/new/", views.job_create, name="job_create"),
    path("jobs/<int:pk>/apply/", views.job_apply, name="job_apply"),
    path("applications/", views.my_applications, name="my_applications"),
    path("applications/all/", views.all_applications, name="all_applications"),
    path(
        "applications/<int:pk>/chat/",
        views.application_conversation,
        name="application_conversation",
    ),
    path("cvs/", views.my_cvs, name="my_cvs"),
    path("cvs/<int:pk>/delete/", views.cv_delete, name="cv_delete"),
]
