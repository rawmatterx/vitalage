"""Settings for the VitalAge web app.

Everything that differs between your laptop and the server comes from
environment variables, so no secret is ever written into the code:

    DJANGO_DEBUG=1          turn on debug pages (laptop only, never on the server)
    DJANGO_SECRET_KEY=...   a long random string (required on the server)
    DJANGO_ALLOWED_HOSTS=   comma-separated web addresses, e.g. vitalage.onrender.com
    DATABASE_URL=...        PostgreSQL address on the server; SQLite is used if unset
"""

import os
import sys
import warnings
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

APP_DIR = Path(__file__).resolve().parent.parent   # .../vitalage/app
REPO_DIR = APP_DIR.parent                          # .../vitalage

# Let the app import the science package (phenoage/) that sits next to app/.
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-key-not-for-the-server"
    else:
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY, or set DJANGO_DEBUG=1 when working on your laptop."
        )

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]
# Render tells the app its own web address in this variable.
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "identity",   # who people are and what they agreed to
    "research",   # health data, keyed by a random participant ID only
    "coordinator",   # dashboard and export for the study coordinator
]

AUTH_USER_MODEL = "identity.Account"
AUTHENTICATION_BACKENDS = ["identity.backends.EmailBackend"]
LOGIN_URL = "signin"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vitalage_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "vitalage_site.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{APP_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# English and Bengali, as decided in the MVP plan. Bengali text lives in
# app/locale/bn/LC_MESSAGES/django.po (see app/README.md, "Translations").
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("bn", "বাংলা")]
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [APP_DIR / "locale"]

# ---- Secrets for personal fields (see identity/crypto.py) ----
# Any long random string. Keep it secret and backed up: without it the
# encrypted emails and birth dates cannot be read.
VITALAGE_FIELD_KEY = os.environ.get("VITALAGE_FIELD_KEY", "")
if not VITALAGE_FIELD_KEY:
    if DEBUG:
        VITALAGE_FIELD_KEY = "dev-only-field-key"
    else:
        raise ImproperlyConfigured("Set VITALAGE_FIELD_KEY to a long random string.")

# The app's public address, used in invite links.
VITALAGE_SITE_URL = os.environ.get("VITALAGE_SITE_URL", "http://127.0.0.1:8000")
if os.environ.get("RENDER_EXTERNAL_URL") and "VITALAGE_SITE_URL" not in os.environ:
    VITALAGE_SITE_URL = os.environ["RENDER_EXTERNAL_URL"]

# ---- Email ----
# With EMAIL_HOST unset (a laptop), emails are printed in the terminal instead
# of being sent. On the server, set these for your email service. Suggested
# free default (a guess, not yet chosen): Brevo SMTP, host smtp-relay.brevo.com,
# port 587, with the SMTP login and key from your Brevo account.
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "VitalAge <no-reply@example.com>")

# Sign-in lasts 30 days on a phone, and ends when the browser is told to sign out.
SESSION_COOKIE_AGE = 30 * 24 * 3600

STATIC_URL = "static/"
STATIC_ROOT = APP_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # On the server, files get a fingerprint in their name so browsers never use an old copy.
    # On a laptop (and in tests) plain storage is used, so collectstatic is not needed.
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
                    else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# On a laptop the collected-files folder does not exist yet; that is fine.
warnings.filterwarnings("ignore", message="No directory at", module="whitenoise.base")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Safety settings that only make sense on the real server (HTTPS).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
