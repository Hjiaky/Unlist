# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

# The browser may load nothing from anywhere but this instance (Tao rule 4).
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)

PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"


class StrictHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response


def operator_exists() -> bool:
    return get_user_model().objects.exists()


class FirstRunMiddleware:
    """Until the Operator account exists, every page leads to the setup page."""

    ALLOWED_PREFIXES = ("/setup/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response
        self._operator_known = False

    def __call__(self, request):
        if not self._operator_known:
            if operator_exists():
                self._operator_known = True
            elif not request.path.startswith(self.ALLOWED_PREFIXES):
                return redirect("setup")
        return self.get_response(request)
