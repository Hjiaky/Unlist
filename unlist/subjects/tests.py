# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from unlist.subjects import consent as consent_module
from unlist.subjects import deletion
from unlist.subjects.consent import ConsentRequired, record_consent, require_consent, withdraw_consent
from unlist.subjects.deletion import delete_subject
from unlist.subjects.models import Consent, IdentifyingDetail, Mailbox, Subject

PASSWORD = "a long enough passphrase"


def make_subject(**kwargs):
    kwargs.setdefault("name", "Ada")
    kwargs.setdefault("country", "DE")
    return Subject.objects.create(**kwargs)


def born_years_ago(years):
    return timezone.localdate().year - years


class ConsentGuardTests(TestCase):
    def test_nothing_can_be_drafted_without_consent(self):
        subject = make_subject()
        with self.assertRaises(ConsentRequired):
            require_consent(subject)
        record_consent(subject, "subject")
        require_consent(subject)
        withdraw_consent(subject)
        with self.assertRaises(ConsentRequired):
            require_consent(subject)

    def test_consent_can_be_recorded_again_after_withdrawal(self):
        subject = make_subject()
        record_consent(subject, "subject")
        withdraw_consent(subject)
        record_consent(subject, "subject")
        require_consent(subject)
        self.assertEqual(subject.consents.count(), 2)

    def test_recording_twice_keeps_one_active_consent(self):
        subject = make_subject()
        record_consent(subject, "subject")
        record_consent(subject, "subject")
        self.assertEqual(subject.consents.count(), 1)

    def test_scope_is_stored_with_the_consent(self):
        consent = record_consent(make_subject(), "subject")
        self.assertIn("Removal Requests", consent.scope)
        self.assertTrue(consent.scope.startswith("v"))

    def test_withdrawal_runs_hooks_and_records_the_date(self):
        subject = make_subject()
        record_consent(subject, "subject")
        seen = []
        hook = lambda s, c: seen.append((s, c))  # noqa: E731
        consent_module.on_withdrawn.append(hook)
        self.addCleanup(consent_module.on_withdrawn.remove, hook)
        withdraw_consent(subject)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], subject)
        self.assertIsNotNone(Consent.objects.get().withdrawn_at)

    def test_withdrawing_without_consent_runs_no_hooks(self):
        seen = []
        hook = lambda s, c: seen.append(1)  # noqa: E731
        consent_module.on_withdrawn.append(hook)
        self.addCleanup(consent_module.on_withdrawn.remove, hook)
        withdraw_consent(make_subject())
        self.assertEqual(seen, [])


class ChildTests(TestCase):
    def test_no_year_of_birth_is_not_a_child(self):
        subject = make_subject()
        self.assertFalse(subject.is_child)
        self.assertFalse(subject.needs_own_involvement)

    def test_adult(self):
        subject = make_subject(year_of_birth=born_years_ago(18))
        self.assertFalse(subject.is_child)
        self.assertFalse(subject.needs_own_involvement)

    def test_young_child(self):
        subject = make_subject(year_of_birth=born_years_ago(11))
        self.assertTrue(subject.is_child)
        self.assertFalse(subject.needs_own_involvement)

    def test_child_from_twelve_needs_own_involvement(self):
        for age in (12, 17):
            subject = make_subject(year_of_birth=born_years_ago(age))
            self.assertTrue(subject.is_child)
            self.assertTrue(subject.needs_own_involvement)


class DeletionTests(TestCase):
    def test_deleting_a_subject_leaves_no_rows(self):
        subject = make_subject()
        Mailbox.objects.create(subject=subject, email="ada@example.org")
        Mailbox.objects.create(subject=subject, email="ada2@example.org", mode=Mailbox.Mode.LIVE)
        IdentifyingDetail.objects.create(
            subject=subject, kind="customer_number", value="123", organization_label="Shop"
        )
        record_consent(subject, "subject")
        other = make_subject(name="Bo")
        Mailbox.objects.create(subject=other, email="bo@example.org")
        delete_subject(subject)
        self.assertEqual(Subject.objects.count(), 1)
        for model in apps.get_app_config("subjects").get_models():
            expected = 1 if model in (Subject, Mailbox) else 0
            self.assertEqual(model.objects.count(), expected, model.__name__)

    def test_every_foreign_key_to_subject_cascades(self):
        for model in apps.get_app_config("subjects").get_models():
            for field in model._meta.get_fields():
                if field.is_relation and field.many_to_one and field.related_model is Subject:
                    self.assertEqual(field.remote_field.on_delete.__name__, "CASCADE", f"{model.__name__}.{field.name}")

    def test_before_delete_hooks_run_first(self):
        subject = make_subject()
        seen = []
        hook = lambda s: seen.append(Subject.objects.filter(pk=s.pk).exists())  # noqa: E731
        deletion.before_delete.append(hook)
        self.addCleanup(deletion.before_delete.remove, hook)
        delete_subject(subject)
        self.assertEqual(seen, [True])
        self.assertFalse(Subject.objects.exists())


class ViewTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("operator", password=PASSWORD)

    def login(self):
        self.client.login(username="operator", password=PASSWORD)

    def test_views_require_login(self):
        subject = make_subject()
        pk = subject.pk
        paths = [
            "/subjects/",
            "/subjects/add/",
            f"/subjects/{pk}/",
            f"/subjects/{pk}/consent/",
            f"/subjects/{pk}/details/add/",
            f"/subjects/{pk}/mailboxes/add/",
            f"/subjects/{pk}/delete/",
        ]
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response["Location"].startswith("/login/"), path)
        for path in [f"/subjects/{pk}/consent/withdraw/", f"/subjects/{pk}/delete/"]:
            self.assertEqual(self.client.post(path).status_code, 302, path)
        self.assertTrue(Subject.objects.filter(pk=pk).exists())

    def add(self, **overrides):
        data = {
            "name": "Ada",
            "country": "DE",
            "email": "ada@example.org",
            "year_of_birth": "",
            "parental_responsibility": "",
        }
        data.update(overrides)
        return self.client.post("/subjects/add/", data)

    def test_add_subject_creates_a_mailbox(self):
        self.login()
        response = self.add()
        subject = Subject.objects.get()
        self.assertRedirects(response, f"/subjects/{subject.pk}/")
        self.assertEqual(subject.mailboxes.get().email, "ada@example.org")
        self.assertEqual(subject.mailboxes.get().mode, "import")

    def test_country_codes_are_validated(self):
        self.login()
        for bad in ["XX", "Germany", "de", ""]:
            self.assertEqual(self.add(country=bad).status_code, 200, bad)
        self.assertEqual(Subject.objects.count(), 0)
        self.add(country="GB")
        self.assertEqual(Subject.objects.get().country, "GB")

    def test_year_of_birth_must_be_plausible(self):
        self.login()
        self.add(year_of_birth="1800")
        self.add(year_of_birth=str(timezone.localdate().year + 1))
        self.assertEqual(Subject.objects.count(), 0)

    def test_consent_flow(self):
        self.login()
        subject = make_subject()
        page = self.client.get(f"/subjects/{subject.pk}/consent/")
        self.assertContains(page, "Removal Requests")
        self.client.post(f"/subjects/{subject.pk}/consent/", {"given_by": "subject"})
        self.assertFalse(subject.has_active_consent())
        self.client.post(f"/subjects/{subject.pk}/consent/", {"given_by": "subject", "confirm": "on"})
        self.assertTrue(subject.has_active_consent())
        self.client.post(f"/subjects/{subject.pk}/consent/withdraw/")
        self.assertFalse(subject.has_active_consent())

    def test_parent_consent_only_offered_for_a_child(self):
        self.login()
        adult = make_subject()
        self.client.post(f"/subjects/{adult.pk}/consent/", {"given_by": "parent", "confirm": "on"})
        self.assertFalse(adult.has_active_consent())
        child = make_subject(name="Kid", year_of_birth=born_years_ago(10))
        self.client.post(f"/subjects/{child.pk}/consent/", {"given_by": "parent", "confirm": "on"})
        self.assertEqual(child.consents.get().given_by, "parent")

    def test_child_note_on_the_detail_page(self):
        self.login()
        teen = make_subject(year_of_birth=born_years_ago(14))
        self.assertContains(self.client.get(f"/subjects/{teen.pk}/"), "own involvement")
        young = make_subject(year_of_birth=born_years_ago(8))
        self.assertNotContains(self.client.get(f"/subjects/{young.pk}/"), "own involvement")

    def test_details_and_mailboxes(self):
        self.login()
        subject = make_subject()
        self.client.post(
            f"/subjects/{subject.pk}/details/add/",
            {"kind": "customer_number", "value": "42", "organization_label": "Shop"},
        )
        detail = subject.details.get()
        self.assertContains(self.client.get(f"/subjects/{subject.pk}/"), "42")
        self.client.post(f"/subjects/{subject.pk}/details/{detail.pk}/remove/")
        self.assertEqual(subject.details.count(), 0)
        self.client.post(f"/subjects/{subject.pk}/mailboxes/add/", {"email": "x@example.org"})
        self.client.post(f"/subjects/{subject.pk}/mailboxes/add/", {"email": "X@example.org"})
        self.assertEqual(subject.mailboxes.count(), 1)

    def test_delete_needs_confirmation_then_deletes(self):
        self.login()
        subject = make_subject()
        self.assertContains(self.client.get(f"/subjects/{subject.pk}/delete/"), "cannot be undone")
        self.assertTrue(Subject.objects.exists())
        self.client.post(f"/subjects/{subject.pk}/delete/")
        self.assertFalse(Subject.objects.exists())

    def test_detail_of_unknown_subject_is_404(self):
        self.login()
        self.assertEqual(self.client.get("/subjects/999/").status_code, 404)
