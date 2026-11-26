# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from unlist.organizations import hooks, loading
from unlist.organizations.models import LocalOverride, Organization, OrganizationList, PendingContactChange
from unlist.organizations.tests.helpers import as_bytes, document, subscribed_list

ACME = {"slug": "acme", "name": "ACME Ltd", "email": "privacy@acme.example", "domains": ["acme.example"]}


class ViewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)
        self.high = subscribed_list("https://lists.example/high.json", position=0)
        self.low = subscribed_list("https://lists.example/low.json", position=1)
        loading.apply_list_document(
            self.high, document([ACME, {"slug": "beta", "name": "Beta Broker", "broker": True}], name="High")
        )
        loading.apply_list_document(self.low, document([{**ACME, "email": "other@acme.example"}], name="Low"))
        loading.recompute()

    def test_pages_need_login(self):
        self.client.logout()
        for url in ["/organizations/", "/organizations/o/acme/", "/organizations/lists/", "/organizations/pending/"]:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_list_and_search(self):
        response = self.client.get("/organizations/")
        self.assertContains(response, "ACME Ltd")
        self.assertContains(response, "Broker")
        response = self.client.get("/organizations/", {"q": "acme.example"})
        self.assertContains(response, "ACME Ltd")
        self.assertNotContains(response, "Beta Broker")

    def test_detail_shows_sources_and_conflicts(self):
        response = self.client.get("/organizations/o/acme/")
        self.assertContains(response, "privacy@acme.example")
        self.assertContains(response, "Lists disagree")
        self.assertContains(response, "other@acme.example")
        self.assertContains(response, "High")
        self.assertNotContains(response, 'style="')

    def test_override_form_and_export(self):
        response = self.client.post("/organizations/o/acme/override/", {"field": "email", "value": "dpo@acme.example"})
        self.assertRedirects(response, "/organizations/o/acme/", fetch_redirect_response=False)
        self.assertEqual(Organization.objects.get(slug="acme").email, "dpo@acme.example")
        self.assertContains(self.client.get("/organizations/o/acme/"), "local override")
        export = self.client.get("/organizations/o/acme/export/")
        self.assertEqual(export["Content-Disposition"], 'attachment; filename="acme.json"')
        self.assertEqual(json.loads(export.content)["email"], "dpo@acme.example")
        override = LocalOverride.objects.get()
        self.client.post(f"/organizations/o/acme/override/{override.pk}/delete/")
        self.assertEqual(Organization.objects.get(slug="acme").email, "privacy@acme.example")

    def test_invalid_override_is_refused(self):
        self.client.post("/organizations/o/acme/override/", {"field": "email", "value": "not-an-email"})
        self.assertFalse(LocalOverride.objects.exists())
        self.client.post("/organizations/o/acme/override/", {"field": "domains", "value": "gmail.com"})
        self.assertFalse(LocalOverride.objects.exists())

    def test_lists_page_reorder_and_update(self):
        response = self.client.get("/organizations/lists/")
        self.assertContains(response, "Update lists")
        self.client.post(f"/organizations/lists/{self.low.pk}/move/", {"direction": "up"})
        self.assertEqual(list(OrganizationList.objects.values_list("name", flat=True)), ["Low", "High"])
        self.assertEqual(Organization.objects.get(slug="acme").email, "other@acme.example")
        with mock.patch.object(loading, "fetch_url", return_value=as_bytes(document([ACME], name="High"))) as fetch:
            response = self.client.post("/organizations/lists/update/")
        self.assertEqual(fetch.call_count, 2)
        self.assertRedirects(response, "/organizations/lists/", fetch_redirect_response=False)

    def test_add_and_remove_a_list(self):
        with mock.patch.object(loading, "fetch_url", return_value=as_bytes(document([], name="Third"))):
            self.client.post("/organizations/lists/add/", {"url": "https://lists.example/third.json"})
        third = OrganizationList.objects.get(name="Third")
        self.client.post(f"/organizations/lists/{third.pk}/remove/")
        self.assertFalse(OrganizationList.objects.filter(pk=third.pk).exists())

    def test_update_needs_post(self):
        with mock.patch.object(loading, "fetch_url") as fetch:
            self.assertEqual(self.client.get("/organizations/lists/update/").status_code, 405)
        fetch.assert_not_called()

    def test_pending_change_side_by_side_and_accept(self):
        hooks.has_case.append(lambda slug: True)
        self.addCleanup(hooks.has_case.clear)
        loading.apply_list_document(self.high, document([{**ACME, "email": "new@acme.example"}], name="High"))
        loading.recompute()
        change = PendingContactChange.objects.get()
        response = self.client.get("/organizations/pending/")
        self.assertContains(response, "privacy@acme.example")
        self.assertContains(response, "new@acme.example")
        self.client.post(f"/organizations/pending/{change.pk}/", {"decision": "accept"})
        self.assertEqual(Organization.objects.get(slug="acme").email, "new@acme.example")
