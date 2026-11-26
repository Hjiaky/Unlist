# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from unlist import crypto
from unlist.core import scheduler
from unlist.core.models import LoginFailure

PASSWORD = "a long enough passphrase"


def make_operator():
    return get_user_model().objects.create_user("operator", password=PASSWORD)


class FirstRunTests(TestCase):
    def test_every_page_leads_to_setup_until_the_operator_exists(self):
        for path in ["/", "/login/"]:
            response = self.client.get(path)
            self.assertRedirects(response, "/setup/", fetch_redirect_response=False)

    def test_setup_creates_the_operator_and_logs_in(self):
        response = self.client.post("/setup/", {"username": "operator", "password1": PASSWORD, "password2": PASSWORD})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_setup_is_gone_once_the_operator_exists(self):
        make_operator()
        response = self.client.post("/setup/", {"username": "intruder", "password1": PASSWORD, "password2": PASSWORD})
        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_short_passwords_are_refused(self):
        self.client.post("/setup/", {"username": "operator", "password1": "short", "password2": "short"})
        self.assertEqual(get_user_model().objects.count(), 0)


class LoginTests(TestCase):
    def setUp(self):
        make_operator()

    def test_home_requires_login(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/", fetch_redirect_response=False)

    def test_login_and_logout(self):
        response = self.client.post("/login/", {"username": "operator", "password": PASSWORD})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.client.post("/logout/")
        self.assertEqual(self.client.get("/").status_code, 302)

    @override_settings(LOGIN_MAX_FAILURES=3)
    def test_repeated_failures_block_further_attempts(self):
        for _ in range(3):
            self.assertEqual(self.client.post("/login/", {"username": "operator", "password": "x"}).status_code, 200)
        blocked = self.client.post("/login/", {"username": "operator", "password": PASSWORD})
        self.assertEqual(blocked.status_code, 429)
        self.assertFalse(self.client.session.get("_auth_user_id"))

    @override_settings(LOGIN_MAX_FAILURES=3)
    def test_failures_are_counted_per_address(self):
        for _ in range(3):
            self.client.post("/login/", {"username": "operator", "password": "x"}, REMOTE_ADDR="10.0.0.9")
        ok = self.client.post("/login/", {"username": "operator", "password": PASSWORD}, REMOTE_ADDR="10.0.0.8")
        self.assertEqual(ok.status_code, 302)

    def test_success_clears_failures(self):
        self.client.post("/login/", {"username": "operator", "password": "x"})
        self.client.post("/login/", {"username": "operator", "password": PASSWORD})
        self.assertEqual(LoginFailure.objects.count(), 0)


class NothingFromElsewhereTests(TestCase):
    """Tao rule 4: pages load nothing from any other host, and the browser is told so."""

    URL_ATTR = re.compile(r"""(?:src|href|action)\s*=\s*["']([^"']*)["']""", re.IGNORECASE)

    def assert_only_local_urls(self, html):
        for url in self.URL_ATTR.findall(html):
            self.assertFalse(re.match(r"^(?:[a-z][a-z0-9+.-]*:)?//", url, re.IGNORECASE), f"external URL: {url}")

    def test_pages_reference_only_this_instance(self):
        self.assert_only_local_urls(self.client.get("/setup/").content.decode())
        make_operator()
        self.assert_only_local_urls(self.client.get("/login/").content.decode())
        self.client.login(username="operator", password=PASSWORD)
        self.assert_only_local_urls(self.client.get("/").content.decode())

    def test_strict_headers(self):
        response = self.client.get("/setup/")
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")

    def test_static_files_are_served_by_the_app(self):
        with override_settings(STATIC_ROOT=Path(__file__).resolve().parent / "static"):
            response = self.client.get("/static/unlist/unlist.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age", response["Cache-Control"])

    def test_htmx_is_vendored_with_its_licence(self):
        static = Path(__file__).resolve().parent / "static" / "unlist"
        self.assertTrue((static / "htmx.min.js").read_text().startswith("/*! htmx 2.0.11 | Zero-Clause BSD"))
        self.assertIn("Zero-Clause BSD", (static / "htmx.LICENSE.txt").read_text())


class CryptoTests(TestCase):
    def setUp(self):
        crypto.reset_cache()
        self.addCleanup(crypto.reset_cache)

    def test_round_trip(self):
        with mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()}):
            token = crypto.encrypt("app-password-123")
            self.assertNotIn("app-password-123", token)
            self.assertEqual(crypto.decrypt(token), "app-password-123")

    def test_a_different_key_cannot_read_it(self):
        with mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()}):
            token = crypto.encrypt("secret")
        crypto.reset_cache()
        with mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()}):
            with self.assertRaises(crypto.WrongKey):
                crypto.decrypt(token)

    def test_missing_key_is_reported_plainly(self):
        env = {k: v for k, v in os.environ.items() if k != "UNLIST_KEY"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(crypto, "KEY_FILE", Path("/nonexistent/unlist.key")),
        ):
            with self.assertRaises(crypto.MissingKey):
                crypto.encrypt("x")


class BootstrapTests(TestCase):
    def test_creates_state_and_a_key_outside_the_data_directory(self):
        from unlist import bootstrap

        with tempfile.TemporaryDirectory() as tmp:
            data, key = Path(tmp) / "data", Path(tmp) / "key" / "unlist.key"
            env = {k: v for k, v in os.environ.items() if k != "UNLIST_KEY"}
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch.object(bootstrap, "DATA_DIR", data),
                mock.patch.object(bootstrap, "KEY_FILE", key),
                mock.patch("sys.stderr", StringIO()),
            ):
                bootstrap.ensure_state()
                first_key = key.read_text()
                bootstrap.ensure_state()  # second start changes nothing
            self.assertTrue((data / "django_secret").exists())
            self.assertTrue((data / "attachments").is_dir())
            self.assertEqual(key.read_text(), first_key)
            self.assertFalse(str(key).startswith(str(data)))
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)


class SchedulerTests(TestCase):
    def test_runs_jobs_and_survives_a_failing_one(self):
        def ok(now):
            return "did something"

        def broken(now):
            raise ValueError("boom")

        with mock.patch.object(scheduler, "JOBS", [broken, ok]), self.assertLogs("unlist.scheduler", "ERROR"):
            self.assertEqual(scheduler.run_once(None), {"broken": "failed", "ok": "did something"})

    def test_command_runs_once(self):
        out = StringIO()
        with mock.patch.object(scheduler, "JOBS", [lambda now: "tick"]):
            call_command("run_scheduler", "--once", stdout=out)
        self.assertIn("tick", out.getvalue())
