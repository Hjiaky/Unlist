# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import datetime
import io
import json
import urllib.error
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils.html import escape

from unlist.breaches import catalogue, matching
from unlist.breaches.models import Breach, BreachAssignment, BreachCatalogue
from unlist.cases.models import Case
from unlist.mail.models import Discovery
from unlist.organizations import loading
from unlist.organizations.tests.helpers import document, subscribed_list
from unlist.subjects.models import Subject

ATTRIBUTION_TEXT = "Breach data from"
ATTRIBUTION_LINK = "https://haveibeenpwned.com"


def record(name, domain="", date="2020-06-01", **extra):
    base = {
        "Name": name,
        "Title": f"{name} title",
        "Domain": domain,
        "BreachDate": date,
        "AddedDate": "2021-01-02T03:04:05Z",
        "DataClasses": ["Email addresses", "Passwords"],
        "IsVerified": True,
        "IsFabricated": False,
        "IsSensitive": False,
        "IsSpamList": False,
        "IsMalware": False,
        "Attribution": "",
        "Description": "A <a href='https://evil.example'>breach</a> &amp; more.",
    }
    base.update(extra)
    return base


FIXTURE = [
    record("Acme", "acme.example"),
    record("AcmeShop", "shop.acme.example", date="2019-01-01"),
    record("Other", "other.example"),
    record("NoDomain", ""),
    record("SpamAcme", "acme.example", IsSpamList=True),
    record("MalwareAcme", "acme.example", IsMalware=True),
    record("FakeAcme", "acme.example", IsFabricated=True),
    record("Credited", "acme.example", Attribution="Thanks to Example Researcher"),
]

ACME = {"slug": "acme", "name": "ACME Ltd", "email": "privacy@acme.example", "domains": ["acme.example"]}
OTHER = {"slug": "other", "name": "Other Inc", "email": "privacy@other.example", "domains": ["other.example"]}


def at(year, month, day):
    return datetime.datetime(year, month, day, tzinfo=datetime.UTC)


class Base(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)
        organization_list = subscribed_list("https://lists.example/one.json", position=0)
        loading.apply_list_document(organization_list, document([ACME, OTHER]))
        loading.recompute()
        from unlist.organizations.models import Organization

        self.acme = Organization.objects.get(slug="acme")
        self.other = Organization.objects.get(slug="other")
        catalogue.store(FIXTURE, source=catalogue.SOURCE_URL, fetched_at=at(2026, 1, 1), bundled=True)
        self.subject = Subject.objects.create(name="Sam", country="NL")

    def discover(self, organization, first, last):
        return Discovery.objects.create(
            subject=self.subject, organization=organization, first_seen=first, last_seen=last
        )

    def names(self, rows):
        return sorted(row["breach"].name for row in rows)


class MatchingTests(Base):
    def test_domain_and_subdomain_match_by_registrable_domain(self):
        self.discover(self.acme, at(2018, 1, 1), at(2022, 1, 1))
        # Credited and Acme at acme.example, AcmeShop at shop.acme.example; spam, malware, fabricated left out.
        self.assertEqual(self.names(matching.rows_for_subject(self.subject)), ["Acme", "AcmeShop", "Credited"])

    def test_other_organization_does_not_match(self):
        self.discover(self.other, None, None)
        self.assertEqual(self.names(matching.rows_for_subject(self.subject)), ["Other"])

    def test_excluded_breaches_have_no_organization(self):
        for name in ["SpamAcme", "MalwareAcme", "FakeAcme"]:
            self.assertIsNone(matching.organization_for(Breach.objects.get(name=name)), name)

    def test_excluded_breach_cannot_be_assigned(self):
        response = self.client.post("/breaches/assign/SpamAcme/", {"organization": "acme"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BreachAssignment.objects.exists())

    def test_hand_assignment_by_name(self):
        self.discover(self.other, None, None)
        self.assertNotIn("NoDomain", self.names(matching.rows_for_subject(self.subject)))
        response = self.client.post("/breaches/assign/NoDomain/", {"organization": "other"})
        self.assertRedirects(response, "/breaches/assign/NoDomain/")
        self.assertEqual(BreachAssignment.objects.get().organization, self.other)
        self.assertEqual(self.names(matching.rows_for_subject(self.subject)), ["NoDomain", "Other"])
        self.client.post("/breaches/assign/NoDomain/remove/")
        self.assertNotIn("NoDomain", self.names(matching.rows_for_subject(self.subject)))

    def test_assignment_survives_a_reload(self):
        BreachAssignment.objects.create(breach_name="NoDomain", organization=self.acme)
        catalogue.store(FIXTURE, source=catalogue.SOURCE_URL, fetched_at=at(2026, 2, 1), bundled=False)
        self.assertEqual(BreachAssignment.objects.count(), 1)

    def test_cases_count_without_a_discovery(self):
        Case.objects.create(subject=self.subject, organization=self.other, reference="U-TEST")
        rows = matching.rows_for_subject(self.subject)
        self.assertEqual(self.names(rows), ["Other"])
        self.assertEqual(rows[0]["timing"], matching.UNKNOWN)

    def test_assignment_search_finds_organizations(self):
        response = self.client.get("/breaches/assign/NoDomain/", {"q": "acme.example"})
        self.assertContains(response, "ACME Ltd")
        self.assertNotContains(response, "Other Inc")


class TimingTests(Base):
    def test_while_before_after(self):
        first, last = at(2020, 1, 1), at(2021, 1, 1)
        self.assertEqual(matching.timing(datetime.date(2020, 6, 1), first, last), matching.WHILE)
        self.assertEqual(matching.timing(datetime.date(2019, 12, 31), first, last), matching.BEFORE)
        self.assertEqual(matching.timing(datetime.date(2021, 1, 2), first, last), matching.AFTER)
        self.assertEqual(matching.timing(datetime.date(2020, 1, 1), first, last), matching.WHILE)
        self.assertEqual(matching.timing(None, first, last), matching.UNKNOWN)
        self.assertEqual(matching.timing(datetime.date(2020, 6, 1), None, None), matching.UNKNOWN)

    def test_page_wording_and_case_links(self):
        self.discover(self.acme, at(2019, 6, 1), at(2021, 1, 1))
        response = self.client.get(f"/breaches/subjects/{self.subject.pk}/")
        self.assertContains(response, "While the Subject was known to them")  # Acme, 2020-06-01
        self.assertContains(response, "Before the Subject was known to them")  # AcmeShop, 2019-01-01
        self.assertContains(response, escape(matching.NOT_A_CLAIM))
        self.assertContains(response, "Open a Case")
        case = Case.objects.create(subject=self.subject, organization=self.acme, reference="U-ACME")
        response = self.client.get(f"/breaches/subjects/{self.subject.pk}/")
        self.assertContains(response, f"/cases/{case.pk}/")
        self.assertNotContains(response, "Open a Case")

    def test_after_wording(self):
        self.discover(self.acme, at(2015, 1, 1), at(2016, 1, 1))
        response = self.client.get(f"/breaches/subjects/{self.subject.pk}/")
        self.assertContains(response, "After the Subject was last seen there")

    def test_description_is_text_not_html(self):
        self.discover(self.acme, at(2019, 6, 1), at(2021, 1, 1))
        response = self.client.get(f"/breaches/subjects/{self.subject.pk}/")
        self.assertNotContains(response, "<a href='https://evil.example'>")
        self.assertNotContains(response, "evil.example")
        self.assertContains(response, "A breach &amp; more.")


class AttributionTests(Base):
    def assert_attributed(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        self.assertContains(response, ATTRIBUTION_TEXT, msg_prefix=url)
        self.assertContains(response, "Have I Been Pwned (haveibeenpwned.com)", msg_prefix=url)
        self.assertContains(response, f'href="{ATTRIBUTION_LINK}"', msg_prefix=url)
        self.assertContains(response, "CC BY 4.0", msg_prefix=url)
        return response

    def test_every_view_shows_attribution(self):
        self.discover(self.acme, at(2019, 6, 1), at(2021, 1, 1))
        BreachAssignment.objects.create(breach_name="NoDomain", organization=self.acme)
        for url in [
            "/breaches/",
            f"/breaches/subjects/{self.subject.pk}/",
            "/breaches/assign/",
            "/breaches/assign/NoDomain/",
            "/breaches/assign/Acme/",
        ]:
            self.assert_attributed(url)

    def test_empty_pages_show_attribution_too(self):
        BreachCatalogue.objects.all().delete()
        Breach.objects.all().delete()
        for url in ["/breaches/", f"/breaches/subjects/{self.subject.pk}/", "/breaches/assign/"]:
            self.assert_attributed(url)

    def test_the_breachs_own_attribution_is_shown(self):
        self.discover(self.acme, at(2019, 6, 1), at(2021, 1, 1))
        self.assertContains(self.client.get(f"/breaches/subjects/{self.subject.pk}/"), "Thanks to Example Researcher")

    def test_pages_need_login(self):
        self.client.logout()
        for url in ["/breaches/", f"/breaches/subjects/{self.subject.pk}/", "/breaches/assign/"]:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.post("/breaches/update/").status_code, 302)

    def test_licence_file_ships_with_the_data(self):
        text = (catalogue.DATA_DIR / "LICENSE-hibp.txt").read_text(encoding="utf-8")
        for needed in ["CC BY 4.0", catalogue.SOURCE_URL, "Fetched:", "Changes made"]:
            self.assertIn(needed, text)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class UpdateTests(Base):
    def test_get_does_not_fetch(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            response = self.client.get("/breaches/update/")
        self.assertEqual(response.status_code, 405)
        urlopen.assert_not_called()

    def test_viewing_pages_never_fetches(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            self.client.get("/breaches/")
            self.client.get(f"/breaches/subjects/{self.subject.pk}/")
        urlopen.assert_not_called()

    def test_post_fetches_with_user_agent_and_stores(self):
        body = json.dumps([record("Fresh", "fresh.example")]).encode()
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(body)) as urlopen:
            response = self.client.post("/breaches/update/", follow=True)
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://haveibeenpwned.com/api/v3/breaches")
        self.assertIn("Unlist", request.get_header("User-agent"))
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNotNone(urlopen.call_args.kwargs.get("timeout"))
        self.assertEqual(list(Breach.objects.values_list("name", flat=True)), ["Fresh"])
        catalogue_row = BreachCatalogue.objects.get()
        self.assertFalse(catalogue_row.bundled)
        self.assertEqual(catalogue_row.count, 1)
        self.assertContains(response, "1 breaches")
        self.assertContains(response, "outside service")

    def test_failure_changes_nothing(self):
        before = Breach.objects.count()
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            response = self.client.post("/breaches/update/", follow=True)
        self.assertContains(response, "Could not reach Have I Been Pwned")
        self.assertEqual(Breach.objects.count(), before)

    def test_bad_and_oversized_answers_change_nothing(self):
        before = Breach.objects.count()
        for body in [b"not json", b'{"a": 1}', b"[]"]:
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(body)):
                self.client.post("/breaches/update/")
        with mock.patch.object(catalogue, "MAX_BYTES", 5):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"[" + b" " * 20 + b"]")):
                self.client.post("/breaches/update/")
        self.assertEqual(Breach.objects.count(), before)

    def test_index_labels_the_button_as_an_outside_request(self):
        response = self.client.get("/breaches/")
        self.assertContains(response, "Update breach list")
        self.assertContains(response, "outside service")
        self.assertContains(response, "nonfree")


class LoadingTests(TestCase):
    def test_load_breaches_is_idempotent(self):
        out = io.StringIO()
        call_command("load_breaches", stdout=out)
        count = Breach.objects.count()
        self.assertGreater(count, 1000)
        first = BreachCatalogue.objects.get()
        self.assertTrue(first.bundled)
        self.assertEqual(first.count, count)
        out = io.StringIO()
        call_command("load_breaches", stdout=out)
        self.assertIn("already up to date", out.getvalue())
        self.assertEqual(Breach.objects.count(), count)
        self.assertEqual(BreachCatalogue.objects.count(), 1)
        call_command("load_breaches", "--force", stdout=io.StringIO())
        self.assertEqual(Breach.objects.count(), count)

    def test_bundled_file_loads_and_is_usable(self):
        call_command("load_breaches", stdout=io.StringIO())
        breach = Breach.objects.exclude(domain="").first()
        self.assertTrue(breach.name and breach.title)
        self.assertTrue(Breach.objects.filter(domain="").exists())
        self.assertTrue(Breach.objects.filter(is_spam_list=True).exists())
        self.assertEqual(BreachCatalogue.objects.get().fetched_at.date(), datetime.date(2026, 11, 26))

    def test_reload_removes_breaches_the_catalogue_dropped(self):
        catalogue.store(FIXTURE, source="x", fetched_at=at(2026, 1, 1), bundled=True)
        catalogue.store(FIXTURE[:2], source="x", fetched_at=at(2026, 1, 2), bundled=False)
        self.assertEqual(Breach.objects.count(), 2)

    def test_load_command_makes_no_request(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            call_command("load_breaches", stdout=io.StringIO())
        urlopen.assert_not_called()
