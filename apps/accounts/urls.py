from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify-email/", views.verify_email, name="verify_email"),
    path(
        "resend-verification/",
        views.resend_verification,
        name="resend_verification",
    ),
    path(
        "password-reset/",
        views.password_reset_request,
        name="password_reset_request",
    ),
    path(
        "password-reset/<int:uid>/<str:token_value>/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path("profile/", views.profile, name="profile"),
    path("users/", views.user_list, name="user_list"),
    path("users/report.pdf", views.user_export_pdf, name="user_export_pdf"),
    path("platform-settings/", views.platform_settings, name="platform_settings"),
]
