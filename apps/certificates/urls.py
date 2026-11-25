from django.urls import path

from . import views

app_name = "certificates"

urlpatterns = [
    path("", views.certificate_list, name="list"),
    path("<int:pk>/", views.certificate_detail, name="detail"),
    path("<int:pk>/download/", views.download_certificate, name="download"),
    path("claim/<slug:slug>/", views.claim_certificate, name="claim"),
    path("verify/", views.verify_certificate, name="verify_form"),
    path("verify/<str:code>/", views.verify_certificate, name="verify"),
]
