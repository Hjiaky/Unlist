# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import hashlib
import json
import os
import re
import tomllib
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

import unlist
from unlist.legal import licence_check
from unlist.legal.views import SCRIPTS
from unlist.paths import BASE_DIR

PSL_DIR = BASE_DIR / "unlist" / "mail" / "data"


class AboutTests(TestCase):
    def test_reachable_before_setup_and_without_login(self):
        self.assertFalse(get_user_model().objects.exists())
        for path in ["/about/", "/about/licence/", "/about/notices/", "/about/javascript/"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_reachable_without_login_once_the_operator_exists(self):
        get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.assertEqual(self.client.get("/about/").status_code, 200)

    def test_about_page_has_notices_and_source_link(self):
        body = self.client.get("/about/").content.decode()
        self.assertIn("Copyright (C) 2026 The Unlist contributors", body)
        self.assertIn("GNU Affero General Public License", body)
        self.assertIn("WITHOUT ANY WARRANTY", body)
        self.assertIn(unlist.__version__, body)
        self.assertIn(f'href="https://github.com/Hjiaky/Unlist/tree/v{unlist.__version__}"', body)
        for link in ["/about/licence/", "/about/notices/", "/about/javascript/"]:
            self.assertIn(f'href="{link}"', body)
        self.assertIn("UNLIST_SOURCE_URL", body)

    def test_source_url_environment_variable_overrides_the_link(self):
        with mock.patch.dict(os.environ, {"UNLIST_SOURCE_URL": "https://example.org/my/fork"}):
            about = self.client.get("/about/").content.decode()
            login = self.client.get("/login/", follow=True).content.decode()
        self.assertIn('href="https://example.org/my/fork"', about)
        self.assertNotIn("github.com/Hjiaky/Unlist/tree", about)
        self.assertIn('href="https://example.org/my/fork"', login)

    def test_source_url_that_is_not_http_is_ignored(self):
        with mock.patch.dict(os.environ, {"UNLIST_SOURCE_URL": "javascript:alert(1)"}):
            body = self.client.get("/about/").content.decode()
        self.assertNotIn("javascript:alert", body)
        self.assertIn(f"tree/v{unlist.__version__}", body)

    def test_footer_source_link_on_the_login_page(self):
        get_user_model().objects.create_user("operator", password="a long enough passphrase")
        body = self.client.get("/login/").content.decode()
        self.assertIn("Unlist is free software (AGPL-3.0-or-later)", body)
        self.assertIn(f'<a href="https://github.com/Hjiaky/Unlist/tree/v{unlist.__version__}">Source</a>', body)
        self.assertIn('<a href="/about/">About</a>', body)

    def test_licence_and_notices_are_plain_text(self):
        for path, marker in [("/about/licence/", "GNU AFFERO GENERAL PUBLIC LICENSE"), ("/about/notices/", "Django")]:
            response = self.client.get(path)
            self.assertTrue(response["Content-Type"].startswith("text/plain"), path)
            self.assertIn(marker, response.content.decode())

    def test_javascript_labels_table_lists_htmx(self):
        body = self.client.get("/about/javascript/").content.decode()
        self.assertIn('id="jslicense-labels1"', body)
        self.assertIn("/static/unlist/htmx.min.js", body)
        self.assertIn("0BSD", body)
        self.assertIn("https://github.com/bigskysoftware/htmx", body)

    def test_every_script_a_page_loads_is_in_the_table(self):
        page = self.client.get("/about/").content.decode()
        sources = re.findall(r'<script[^>]*\ssrc="([^"]+)"', page)
        self.assertTrue(sources)
        listed = {"/static/" + script["path"] for script in SCRIPTS}
        self.assertLessEqual(set(sources), listed)


class VersionTests(SimpleTestCase):
    def test_version_matches_pyproject(self):
        with open(BASE_DIR / "pyproject.toml", "rb") as handle:
            self.assertEqual(tomllib.load(handle)["project"]["version"], unlist.__version__)


class PublicSuffixListTests(SimpleTestCase):
    def test_file_starts_with_its_mpl_header(self):
        data = (PSL_DIR / "public_suffix_list.dat").read_bytes()
        self.assertTrue(data.startswith(b"// This Source Code Form is subject to the terms of the Mozilla Public\n"))
        self.assertIn(b"https://mozilla.org/MPL/2.0/", data[:300])

    def test_file_is_unmodified(self):
        record = json.loads((PSL_DIR / "public-suffix-list.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256((PSL_DIR / record["file"]).read_bytes()).hexdigest()
        self.assertEqual(digest, record["sha256"])
        self.assertEqual(record["licence"], "MPL-2.0")

    def test_readme_and_licence_text_sit_next_to_it(self):
        readme = (PSL_DIR / "PUBLIC-SUFFIX-LIST-README.md").read_text(encoding="utf-8")
        record = json.loads((PSL_DIR / "public-suffix-list.json").read_text(encoding="utf-8"))
        self.assertIn(record["commit"], readme)
        self.assertIn(record["snapshot_date"], readme)
        self.assertIn("Mozilla Public License", (PSL_DIR / "LICENSE.MPL-2.0").read_text(encoding="utf-8")[:100])


class CheckLicencesTests(SimpleTestCase):
    def run_command(self):
        out = StringIO()
        call_command("check_licences", stdout=out)
        return out.getvalue()

    def test_passes_for_the_installed_packages(self):
        output = self.run_command()
        self.assertIn("Django", output)
        self.assertNotIn("ruff", output)
        self.assertNotIn("pip ", output)

    def test_allow_list_only_has_agpl_compatible_licences(self):
        allow_list = json.loads(licence_check.ALLOW_LIST.read_text(encoding="utf-8"))
        for name, expression in allow_list.items():
            for token in re.split(r"\s+(?:AND|OR|WITH)\s+", expression):
                self.assertIn(token, licence_check.AGPL_COMPATIBLE, name)

    def test_fails_when_an_extra_runtime_distribution_appears(self):
        real_distribution = licence_check.distribution

        class FakeDistribution:
            version = "1.0"
            requires = None
            metadata = {"Name": "fakepkg", "License-Expression": "MIT"}

        def fake_distribution(name):
            if name == "fakepkg":
                return FakeDistribution()
            return real_distribution(name)

        with (
            mock.patch.object(licence_check, "read_requirements", return_value=["Django", "gunicorn", "fakepkg"]),
            mock.patch.object(licence_check, "distribution", side_effect=fake_distribution),
        ):
            with self.assertRaises(CommandError) as raised:
                self.run_command()
        message = str(raised.exception)
        self.assertIn("fakepkg: not in unlist/legal/licences.json", message)
        self.assertIn("fakepkg: no section in THIRD-PARTY-NOTICES", message)

    def test_fails_when_the_notices_lack_a_package(self):
        allow_list = json.loads(licence_check.ALLOW_LIST.read_text(encoding="utf-8"))
        notices = licence_check.NOTICES.read_text(encoding="utf-8").replace("=== sqlparse (", "=== renamed (")
        problems, _ = licence_check.check(allow_list, notices, licence_check.read_requirements())
        self.assertEqual(problems, ["sqlparse: no section in THIRD-PARTY-NOTICES"])

    def test_fails_when_a_requirement_is_not_installed(self):
        _, problems = licence_check.runtime_distributions(["definitely-not-installed-package"])
        self.assertEqual(problems, ["definitely-not-installed-package is in requirements.txt but not installed"])

    def test_dev_tools_are_not_runtime_packages(self):
        found, _ = licence_check.runtime_distributions(licence_check.read_requirements())
        for name in ["ruff", "pip", "setuptools"]:
            self.assertNotIn(name, found)
        self.assertLessEqual({"django", "asgiref", "sqlparse", "gunicorn", "cryptography"}, set(found))
