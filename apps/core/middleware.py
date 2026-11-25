from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class AccountStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            status = getattr(user, "account_status", "active")
            if status in {"suspended", "rejected"}:
                logout(request)
                messages.error(request, "This account is not active. Contact support.")
                return redirect("accounts:login")

            if (
                getattr(settings, "PORTAL_REQUIRE_EMAIL_VERIFICATION", False)
                and not getattr(user, "is_verified", False)
                and not request.path.startswith(("/static/", "/media/", "/api/"))
                and request.path
                not in {
                    reverse("accounts:verify_email"),
                    reverse("accounts:resend_verification"),
                    reverse("accounts:logout"),
                }
            ):
                return redirect("accounts:verify_email")

        return self.get_response(request)
