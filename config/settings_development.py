import os

from .settings_base import *

DEBUG = env_bool("DJANGO_DEBUG", True)
SECURE_SSL_REDIRECT = False
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
