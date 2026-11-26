# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import shutil
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile

from unlist import paths
from unlist.organizations import loading
from unlist.organizations.tests.helpers import document, subscribed_list
from unlist.subjects.models import Subject

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BODY_MARKER = "BODYSECRET"

ORGANIZATIONS = [
    {"slug": "bigshop", "name": "Big Shop GmbH", "email": "datenschutz@bigshop.de", "domains": ["bigshop.de"]},
    {"slug": "payco", "name": "PayCo Ltd", "email": "privacy@pay.example", "domains": ["pay.example"]},
    {"slug": "brand", "name": "Brand SE", "email": "privacy@brand.example", "domains": ["brand.example"]},
    {"slug": "streamly", "name": "Streamly Inc.", "email": "privacy@streamly.example", "domains": ["streamly.example"]},
]


def load_organizations():
    loading.apply_list_document(subscribed_list(), document(ORGANIZATIONS))
    loading.recompute()


def fixture_upload(name="discovery.mbox", extra=b""):
    return SimpleUploadedFile(name, (FIXTURES / name).read_bytes() + extra, content_type="application/mbox")


def make_subject(name="Alex"):
    subject = Subject.objects.create(name=name, country="DE")
    subject.mailboxes.create(email="alex@example.org")
    return subject


class DataDirMixin:
    """Points the data directory at a temporary directory for the test."""

    def setUp(self):
        super().setUp()
        self.data_dir = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(paths, "DATA_DIR", self.data_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.data_dir, True)

    def leftover_files(self):
        return [path for path in self.data_dir.rglob("*") if path.is_file()]


def fake_cases_module(open_case):
    """A stand-in for `unlist.cases.services`, which another ticket writes."""
    module = types.ModuleType("unlist.cases.services")
    module.open_case = open_case
    return mock.patch.dict(sys.modules, {"unlist.cases.services": module})
