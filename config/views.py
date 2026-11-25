from django.conf import settings
from django.db import DatabaseError, connection
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course


def home(request):
    """Public landing page; authenticated users go straight to their dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    db_status = {
        "connected": False,
        "engine": connection.vendor,
        "name": settings.DATABASES["default"]["NAME"],
        "version": "",
        "error": "",
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            row = cursor.fetchone()
            db_status["version"] = row[0] if row else ""
            db_status["connected"] = True
    except DatabaseError as exc:
        db_status["error"] = str(exc)

    stats = {"courses": 0, "students": 0, "teachers": 0}
    try:
        stats["courses"] = Course.objects.filter(
            status=Course.Status.PUBLISHED
        ).count()
        stats["students"] = User.objects.filter(role=User.Role.STUDENT).count()
        stats["teachers"] = User.objects.filter(role=User.Role.TEACHER).count()
    except DatabaseError:
        pass

    context = {
        "db_status": db_status,
        "debug": settings.DEBUG,
        "stats": stats,
        "login_url": reverse("accounts:login"),
        "register_url": reverse("accounts:register"),
    }
    return render(request, "home.html", context)


