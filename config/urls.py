from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.accounts import views as account_views
from .views import home

admin.site.site_header = "Site administration"
admin.site.site_title = "Site administration"
admin.site.index_title = "Platform management"

urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", account_views.dashboard, name="dashboard"),
    path("accounts/", include("apps.accounts.urls")),
    path("academic/", include("apps.academic.urls")),
    path("courses/", include("apps.courses.urls")),
    path("", include("apps.learning.urls")),
    path("live/", include("apps.live.urls")),
    path("", include("apps.assessments.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("assistant/", include("apps.ai_assistant.urls")),
    path("certificates/", include("apps.certificates.urls")),
    path("reports/", include("apps.analytics.urls")),
    path("careers/", include("apps.careers.urls")),
    path("scholarships/", include("apps.scholarships.urls")),
    path("community/", include("apps.community.urls")),
    path("events/", include("apps.events.urls")),
    path("support/", include("apps.support.urls")),
    path("api/", include("apps.api.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
