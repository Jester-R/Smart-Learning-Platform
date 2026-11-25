import os

from django.core.exceptions import ImproperlyConfigured

DJANGO_ENV = os.getenv("DJANGO_ENV", "development").strip().lower()

if DJANGO_ENV in {"production", "prod"}:
    from .settings_production import *
elif DJANGO_ENV in {"development", "dev", "local", ""}:
    from .settings_development import *
else:
    raise ImproperlyConfigured(
        "DJANGO_ENV must be development, dev, local, production, or prod."
    )
