# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from unittest import mock

from django.test import TestCase

from unlist.organizations import hooks, loading, lookup, services
from unlist.organizations.models import (
    Domain,
    ListRecord,
    LocalOverride,
    Organization,
    OrganizationList,
    PendingContactChange,
    SupervisoryAuthority,
)
from unlist.organizations.tests.helpers import as_bytes, document, subscribed_list
from unlist.organizations.validation import record_errors

ACME = {"slug": "acme", "name": "ACME Ltd", "email": "privacy@acme.example", "domains": ["acme.example"]}


class BundledListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        loading.load_bundled_lists()

    def test_bundled_lists_load_in_order(self):
        names = list(OrganizationList.objects.values_list("bundled_file", "licence"))
        self.assertEqual(names, [("organizations.json", "CC0-1.0"), ("jdm-domains.json", "MIT")])
        self.assertGreater(Organization.objects.filter(obsolete=False).count(), 3000)
        self.assertEqual(SupervisoryAuthority.objects.count(), 57)

    def test_by_domain_finds_a_known_organization_from_the_snapshot(self):
        schufa = lookup.by_domain("schufa.de")
        self.assertEqual(schufa.slug, "schufa")
        self.assertTrue(schufa.broker)
        self.assertEqual(lookup.by_domain("datenschutz@schufa.de"), schufa)
        self.assertEqual(lookup.by_domain("https://www.schufa.de/en/"), schufa)

    def test_jdm_domains_add_to_official_records(self):
        self.assertEqual(lookup.by_domain("zalando.co.uk").slug, "zalando")
        self.assertIn("zalando.co.uk", Organization.objects.get(slug="zalando").domains)

    def test_ambiguous_domains_match_nothing(self):
        self.assertTrue(lookup.is_ambiguous("gmail.com"))
        self.assertTrue(lookup.is_ambiguous("bounces.sendgrid.net"))
        self.assertIsNone(lookup.by_domain("someone@gmail.com"))
        self.assertFalse(lookup.is_ambiguous("schufa.de"))

    def test_obsolete_slug_redirects(self):
        self.assertEqual(lookup.get("creditreform-boniversum").slug, "infoscore")

    def test_loading_again_does_nothing(self):
        self.assertFalse(loading.load_bundled_lists())

    def test_named_person_email_is_not_published(self):
        organization = Organization.objects.get(slug="acnw3")
        self.assertEqual(organization.email, "")
        self.assertTrue(any("named person" in note for note in organization.notes))


class ApplyListTests(TestCase):
    def setUp(self):
        self.organization_list = subscribed_list()

    def test_invalid_record_is_skipped_and_the_previous_version_kept(self):
        loading.apply_list_document(self.organization_list, document([ACME]))
        broken = {**ACME, "email": "not an email"}
        new = {"slug": "newco", "name": "NewCo"}
        notes = loading.apply_list_document(
            self.organization_list, document([broken, new, {"name": "no slug"}], version="2")
        )
        self.assertEqual(ListRecord.objects.get(slug="acme").data["email"], "privacy@acme.example")
        self.assertTrue(ListRecord.objects.filter(slug="newco").exists())
        self.assertEqual(len(notes), 2)
        self.assertIn("acme: skipped", notes[0])
        self.assertIn("previous version kept", notes[0])
        self.organization_list.refresh_from_db()
        self.assertEqual(self.organization_list.notes, notes)
        self.assertEqual(self.organization_list.version, "2")

    def test_unusable_file_changes_nothing(self):
        loading.apply_list_document(self.organization_list, document([ACME]))
        bad = document([{"slug": "other", "name": "Other"}])
        bad["header"]["schema_version"] = 99
        with self.assertRaises(loading.ListError):
            loading.apply_list_document(self.organization_list, bad)
        self.assertEqual(list(ListRecord.objects.values_list("slug", flat=True)), ["acme"])

    def test_records_missing_from_a_new_version_are_removed(self):
        loading.apply_list_document(self.organization_list, document([ACME, {"slug": "b", "name": "B"}]))
        loading.apply_list_document(self.organization_list, document([ACME]))
        self.assertEqual(list(ListRecord.objects.values_list("slug", flat=True)), ["acme"])

    def test_a_domain_twice_in_one_list_belongs_to_neither(self):
        twin = {"slug": "twin", "name": "Twin", "domains": ["acme.example"]}
        notes = loading.apply_list_document(self.organization_list, document([ACME, twin]))
        loading.recompute()
        self.assertIn("acme.example: claimed by acme, twin", notes[0])
        self.assertIsNone(lookup.by_domain("acme.example"))


class RecomputeTests(TestCase):
    def setUp(self):
        self.high = subscribed_list("https://lists.example/high.json", position=0)
        self.low = subscribed_list("https://lists.example/low.json", position=1)

    def load(self, high, low=()):
        loading.apply_list_document(self.high, document(list(high), name="High"))
        loading.apply_list_document(self.low, document(list(low), name="Low"))
        loading.recompute()

    def test_merged_fields_name_their_source_and_conflicts(self):
        self.load([ACME], [{**ACME, "email": "other@acme.example", "phone": "+44 20 1"}])
        acme = Organization.objects.get(slug="acme")
        self.assertEqual(acme.email, "privacy@acme.example")
        self.assertEqual(acme.phone, "+44 20 1")
        self.assertEqual(acme.field_sources["email"], "High")
        self.assertEqual(acme.field_sources["phone"], "Low")
        self.assertEqual(acme.conflicts["email"][1], ["Low", "other@acme.example"])

    def test_local_override_wins_and_survives_recompute(self):
        self.load([ACME])
        services.set_override("acme", "email", "dpo@acme.example")
        loading.recompute()
        self.assertEqual(Organization.objects.get(slug="acme").email, "dpo@acme.example")

    def test_domain_matching_merges_records_with_different_slugs(self):
        self.load([ACME], [{"slug": "acme-uk", "name": "ACME UK", "domains": ["acme.example", "acme.co.uk"]}])
        self.assertEqual(Organization.objects.filter(obsolete=False).count(), 1)
        self.assertEqual(lookup.by_domain("acme.co.uk").slug, "acme")

    def test_domain_conflict_matches_nothing_until_resolved_locally(self):
        self.load(
            [ACME, {"slug": "beta", "name": "Beta", "domains": ["beta.example"]}],
            [{"slug": "gamma", "name": "Gamma", "domains": ["acme.example", "beta.example"]}],
        )
        self.assertIsNone(lookup.by_domain("acme.example"))
        self.assertIsNone(lookup.by_domain("beta.example"))
        services.set_override("acme", "domains", ["acme.example"])
        self.assertEqual(lookup.by_domain("acme.example").slug, "acme")
        self.assertIsNone(lookup.by_domain("beta.example"))

    def test_obsolete_redirect_is_followed_in_the_database(self):
        loading.apply_list_document(
            self.high,
            document(
                [{"slug": "newco", "name": "NewCo"}],
                obsolete=[{"slug": "oldco", "name": "OldCo", "redirect-to": "newco"}],
            ),
        )
        loading.apply_list_document(
            self.low, document([{"slug": "oldco", "name": "OldCo", "domains": ["oldco.example"]}])
        )
        loading.recompute()
        self.assertEqual(lookup.get("oldco").slug, "newco")
        self.assertEqual(lookup.by_domain("oldco.example").slug, "newco")

    def test_organizations_that_leave_every_list_are_removed_unless_a_case_needs_them(self):
        self.load([ACME, {"slug": "kept", "name": "Kept"}])
        hooks.has_case.append(lambda slug: slug == "kept")
        self.addCleanup(hooks.has_case.clear)
        self.load([])
        self.assertFalse(Organization.objects.filter(slug="acme").exists())
        self.assertFalse(Organization.objects.get(slug="kept").listed)


class ContactReviewTests(TestCase):
    def setUp(self):
        self.organization_list = subscribed_list()
        loading.apply_list_document(self.organization_list, document([ACME]))
        loading.recompute()
        hooks.has_case.append(lambda slug: slug == "acme")
        self.addCleanup(hooks.has_case.clear)

    def update_with(self, record, version="2"):
        with mock.patch.object(
            loading, "fetch_url", return_value=as_bytes(document([record], version=version))
        ) as fetch:
            loading.update_lists()
        fetch.assert_called_once_with("https://lists.example/extra.json")

    def test_changed_contact_of_an_organization_with_a_case_waits_for_acceptance(self):
        self.update_with({**ACME, "email": "new@acme.example", "phone": "+44 20 2"})
        acme = Organization.objects.get(slug="acme")
        self.assertEqual(acme.email, "privacy@acme.example")
        self.assertEqual(acme.phone, "+44 20 2")  # other fields apply at once
        change = PendingContactChange.objects.get(organization=acme)
        self.assertEqual(change.old["email"], "privacy@acme.example")
        self.assertEqual(change.new["email"], "new@acme.example")
        loading.recompute()  # still held, not duplicated
        self.assertEqual(PendingContactChange.objects.count(), 1)
        self.assertEqual(Organization.objects.get(slug="acme").email, "privacy@acme.example")

        services.accept_contact_change(change)
        self.assertEqual(Organization.objects.get(slug="acme").email, "new@acme.example")
        loading.recompute()
        self.assertEqual(Organization.objects.get(slug="acme").email, "new@acme.example")
        self.assertFalse(PendingContactChange.objects.exists())

    def test_rejecting_keeps_the_old_contact_as_a_local_override(self):
        self.update_with({**ACME, "email": "new@acme.example"})
        services.reject_contact_change(PendingContactChange.objects.get())
        self.assertEqual(Organization.objects.get(slug="acme").email, "privacy@acme.example")
        self.assertEqual(LocalOverride.objects.get(field="email").value, "privacy@acme.example")
        self.assertFalse(PendingContactChange.objects.exists())

    def test_without_a_case_the_change_applies_at_once(self):
        hooks.has_case.clear()
        self.update_with({**ACME, "email": "new@acme.example"})
        self.assertEqual(Organization.objects.get(slug="acme").email, "new@acme.example")
        self.assertFalse(PendingContactChange.objects.exists())


class FetchTests(TestCase):
    def test_update_fetch_is_mocked_and_failure_keeps_the_previous_version(self):
        organization_list = subscribed_list()
        loading.apply_list_document(organization_list, document([ACME]))
        with mock.patch.object(loading, "fetch_url", side_effect=OSError("unreachable")):
            results = loading.update_lists()
        self.assertEqual(results, {organization_list.pk: False})
        organization_list.refresh_from_db()
        self.assertIn("unreachable", organization_list.last_error)
        self.assertTrue(ListRecord.objects.filter(slug="acme").exists())

    def test_bundled_lists_are_never_fetched(self):
        OrganizationList.objects.create(name="bundled", bundled=True, bundled_file="organizations.json")
        with mock.patch.object(loading, "fetch_url") as fetch:
            loading.update_lists()
        fetch.assert_not_called()

    def test_fetch_names_unlist_and_refuses_other_schemes(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"{}"
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(loading.fetch_url("https://lists.example/x.json"), b"{}")
        request = urlopen.call_args.args[0]
        self.assertIn("Unlist", request.get_header("User-agent"))
        with self.assertRaises(loading.ListError):
            loading.fetch_url("file:///etc/passwd")

    def test_add_list_fetches_it_once(self):
        with mock.patch.object(loading, "fetch_url", return_value=as_bytes(document([ACME], name="Extra"))):
            organization_list = services.add_list("https://lists.example/extra.json")
        self.assertEqual(organization_list.name, "Extra")
        self.assertEqual(lookup.by_domain("acme.example").slug, "acme")


class StubTests(TestCase):
    def test_create_stub(self):
        stub = services.create_stub("shop.example", "The Shop")
        self.assertEqual(stub.quality, "local")
        self.assertFalse(stub.has_contact)
        self.assertFalse(stub.contact_confirmed)
        self.assertEqual(lookup.by_domain("orders@shop.example"), stub)
        loading.recompute()  # survives a recompute
        self.assertEqual(lookup.by_domain("shop.example").slug, stub.slug)
        self.assertEqual(Organization.objects.get(slug=stub.slug).quality, "local")
        services.set_override(stub.slug, "email", "privacy@shop.example")
        self.assertTrue(Organization.objects.get(slug=stub.slug).contact_confirmed)

    def test_create_stub_returns_a_known_organization(self):
        organization_list = subscribed_list()
        loading.apply_list_document(organization_list, document([ACME]))
        loading.recompute()
        self.assertEqual(services.create_stub("mail.acme.example").slug, "acme")

    def test_no_stub_for_shared_domains(self):
        with self.assertRaises(ValueError):
            services.create_stub("gmail.com")
        self.assertFalse(Domain.objects.exists())


class ContributionTests(TestCase):
    def test_export_contains_the_overrides_in_the_list_format(self):
        organization_list = subscribed_list()
        loading.apply_list_document(organization_list, document([ACME]))
        loading.recompute()
        services.set_override("acme", "email", "dpo@acme.example", note="seen on their privacy page")
        record = services.contribution(Organization.objects.get(slug="acme"))
        self.assertEqual(record, {"slug": "acme", "name": "ACME Ltd", "email": "dpo@acme.example"})
        self.assertEqual(record_errors(record), [])
