# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Django settings.

The only optional configuration is UNLIST_PUBLIC_ORIGIN, for an instance reached through the
Operator's own HTTPS reverse proxy (spec section 14). Everything else has a fixed default.
"""

import os
from urllib.parse import urlsplit

from unlist.paths import BASE_DIR, DATA_DIR

DEBUG = os.environ.get("UNLIST_DEBUG") == "1"

_secret_file = DATA_DIR / "django_secret"
if _secret_file.exists():
    SECRET_KEY = _secret_file.read_text().strip()
elif DEBUG or os.environ.get("UNLIST_TESTING") == "1":
    SECRET_KEY = "insecure-development-key"
else:
    raise RuntimeError(f"Missing {_secret_file}: run `python -m unlist.bootstrap` first.")

# Reached directly on the local network by default. When the Operator puts Unlist behind
# their own HTTPS reverse proxy, they set UNLIST_PUBLIC_ORIGIN=https://unlist.example.org.
PUBLIC_ORIGIN = os.environ.get("UNLIST_PUBLIC_ORIGIN", "").rstrip("/")
BEHIND_PROXY = bool(PUBLIC_ORIGIN)

if BEHIND_PROXY:
    ALLOWED_HOSTS = [urlsplit(PUBLIC_ORIGIN).hostname, "localhost", "127.0.0.1"]
    CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
else:
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "unlist.core",
    "unlist.subjects",
    "unlist.organizations",
    "unlist.cases",
    "unlist.mail",
    "unlist.breaches",
    "unlist.stats",
    "unlist.llm",
    "unlist.legal",
    "unlist.backup",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "unlist.core.middleware.StrictHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "unlist.core.middleware.FirstRunMiddleware",
]

ROOT_URLCONF = "unlist.urls"
WSGI_APPLICATION = "unlist.wsgi.application"

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
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "unlist.sqlite3",
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;",
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Login throttling: per client address, this many failures within the window block
# further attempts until the window has passed.
LOGIN_MAX_FAILURES = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

LANGUAGE_CODE = "en"
TIME_ZONE = os.environ.get("TZ", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
