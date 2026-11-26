# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The household UI (#53): every page renders, the sidebar, "Needs you", batch approval, filters,
the Table / Board toggle and the first run."""

import re
from datetime import timedelta
from unittest import mock
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone

from unlist.breaches.models import Breach
from unlist.cases import services, storage
from unlist.cases.models import Case, Draft, Reply
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.cases.tests.mail import DataDirMixin
from unlist.core import household
from unlist.mail import importer, scanner
from unlist.mail.models import Discovery, ImportRun, MailboxConnection, UnassignedSender
from unlist.mail.tests.helpers import fixture_upload
from unlist.organizations.loading import load_supervisory_authorities
from unlist.organizations.models import OrganizationList, PendingContactChange
from unlist.subjects.models import Mailbox, Subject

PASSWORD = "a long enough passphrase"


def login(test):
    user = get_user_model().objects.create_user("operator", password=PASSWORD)
    test.client.force_login(user)
    return user


def reply(subject, case=None, key="k1", subject_line="Re: your request"):
    return Reply.objects.create(
        subject=subject,
        case=case,
        source=Reply.Source.UPLOAD,
        dedup_key=key,
        from_address="privacy@acme.example",
        received_at=timezone.now(),
        subject_line=subject_line,
    )


class HouseholdMixin(DataDirMixin):
    """A household with a Case in most states, replies, discoveries and the other records pages show."""

    def build(self):
        load_supervisory_authorities()
        self.subject = make_subject()
        self.other = make_subject(name="Sam Example", email="sam@example.org")
        self.shop = make_organization("acme", "ACME Ltd")
        self.broker = make_organization("databroker", "Data Broker GmbH", broker=True, email="dp@broker.example")
        self.refuser = make_organization("refuser", "Refuser SA", email="dpo@refuser.example")
        self.quiet = make_organization("quiet", "Quiet AG", email="dp@quiet.example")

        # Awaiting approval.
        self.awaiting = services.open_case(self.subject, self.shop, on=DAY0)
        # Paused: the Broker asked for ID or details.
        self.paused = services.open_case(self.subject, self.broker, on=DAY0)
        send(self.paused, DAY0)
        services.record_outcome(self.paused, "id_or_details_asked", on=DAY0 + timedelta(days=5))
        # Complaint draft after a refusal.
        self.complaint = services.open_case(self.subject, self.refuser, on=DAY0)
        send(self.complaint, DAY0)
        services.record_outcome(self.complaint, "refused", on=DAY0 + timedelta(days=9), exception="Art. 17(3)")
        services.draft_complaint(self.complaint, on=DAY0 + timedelta(days=10))
        # Overdue, for the other Subject.
        self.overdue = services.open_case(self.other, self.quiet, on=DAY0)
        send(self.overdue, DAY0)
        services.mark_overdue_if_due(self.overdue, today=DAY0 + timedelta(days=60))
        for case in (self.awaiting, self.paused, self.complaint, self.overdue):
            case.refresh_from_db()

        # A handed-over draft for the other Subject (approved, not yet sent).
        self.handed = services.open_case(self.other, self.shop, on=DAY0)
        self.handed_draft = self.handed.pending_draft
        services.approve(self.handed_draft, on=DAY0)

        self.letter = services.authority_letter(self.paused, "Operator")
        self.attachment = storage.store_upload(self.paused, SimpleUploadedFile("answer.pdf", b"%PDF-1.4"))
        self.matched = reply(self.subject, self.paused, key="m1")
        self.unmatched = reply(self.other, None, key="u1", subject_line="Who is this?")

        self.discovery = Discovery.objects.create(
            subject=self.subject, organization=make_organization("found", "Found Shop"), evidence=scanner.ACCOUNT
        )
        self.sender = UnassignedSender.objects.create(subject=self.subject, domain="unknown.example")
        ImportRun.objects.create(subject=self.subject, finished_at=timezone.now(), total=3)
        mailbox = self.subject.mailboxes.get()
        self.connection = MailboxConnection.objects.create(
            mailbox=mailbox, imap_host="imap.example.org", smtp_host="smtp.example.org", username="alex"
        )
        self.organization_list = OrganizationList.objects.create(name="A list", url="https://lists.example/o.json")
        PendingContactChange.objects.create(organization=self.shop, old={"email": "a@acme.example"}, new={})
        Breach.objects.create(name="SomeBreach", title="Some Breach")


def url_names(resolver=None, namespace=""):
    resolver = resolver or get_resolver()
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            inner = f"{namespace}:{pattern.namespace}" if namespace and pattern.namespace else pattern.namespace
            yield from url_names(pattern, inner or namespace)
        elif isinstance(pattern, URLPattern) and pattern.name:
            yield f"{namespace}:{pattern.name}" if namespace else pattern.name


# Views that only take a POST: a GET is refused (405) or sent back to the page it belongs to.
POST_ONLY = {
    "approve", "logout", "subjects:consent_withdraw", "subjects:detail_remove", "organizations:add_override",
    "organizations:delete_override", "organizations:add_list", "organizations:update_lists",
    "organizations:remove_list", "organizations:move_list", "organizations:toggle_list",
    "organizations:decide_change", "cases:action", "cases:recheck", "cases:reply_upload", "cases:portal",
    "cases:reply_confirm", "cases:reply_dismiss", "cases:reply_assign", "cases:draft_approve",
    "cases:draft_discard", "cases:draft_sent", "cases:early_recheck", "cases:complaint_authority",
    "cases:complaint_uk", "cases:complaint_lodged", "mail:pursue_all", "mail:pursue", "mail:ignore",
    "mail:unignore", "mail:ignore_sender", "mail:unignore_sender", "mail:test_connection", "mail:scan_now",
    "mail:scheduled_rescans", "mail:disconnect", "breaches:update", "breaches:assign_remove",
    "llm:accept_notice", "llm:sort", "llm:apply_evidence", "llm:adapt_draft", "llm:accept_draft",
    "llm:confirm_contact", "backup:download",
}  # fmt: skip
# Pages that need something this household does not have, and say so by redirecting.
REDIRECTS = {
    "setup": "the Operator exists",
    "login": "already logged in",
    "llm:find_contact": "the LLM is off",
}


class EveryPageTests(HouseholdMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.build()
        login(self)

    def urls(self):
        subject, case = self.subject.pk, self.paused.pk
        mailbox = self.subject.mailboxes.get().pk
        return {
            "home": reverse("home"),
            "settings": reverse("settings"),
            "setup": reverse("setup"),
            "login": reverse("login"),
            "subjects:list": reverse("subjects:list"),
            "subjects:add": reverse("subjects:add"),
            "subjects:detail": reverse("subjects:detail", args=[subject]),
            "subjects:consent": reverse("subjects:consent", args=[Subject.objects.create(name="New", country="DE").pk]),
            "subjects:detail_add": reverse("subjects:detail_add", args=[subject]),
            "subjects:mailbox_add": reverse("subjects:mailbox_add", args=[subject]),
            "subjects:delete": reverse("subjects:delete", args=[subject]),
            "organizations:index": reverse("organizations:index"),
            "organizations:detail": reverse("organizations:detail", args=["databroker"]),
            "organizations:export": reverse("organizations:export", args=["databroker"]),
            "organizations:lists": reverse("organizations:lists"),
            "organizations:pending": reverse("organizations:pending"),
            "cases:list": reverse("cases:list"),
            "cases:new": reverse("cases:new") + "?q=acme",
            "cases:detail": reverse("cases:detail", args=[case]),
            "cases:outcome": reverse("cases:outcome", args=[self.complaint.pk]),
            "cases:details": reverse("cases:details", args=[case]),
            "cases:send_id": reverse("cases:send_id", args=[case]),
            "cases:authority_letter": reverse("cases:authority_letter", args=[case]),
            "cases:authority_letter_show": reverse("cases:authority_letter_show", args=[self.letter.pk]),
            "cases:replies": reverse("cases:replies"),
            "cases:draft_edit": reverse("cases:draft_edit", args=[self.awaiting.pending_draft.pk]),
            "cases:draft_eml": reverse("cases:draft_eml", args=[self.handed_draft.pk]),
            "cases:draft_letter": reverse("cases:draft_letter", args=[self.handed_draft.pk]),
            "cases:attachment": reverse("cases:attachment", args=[self.attachment.pk]),
            "cases:complaint": reverse("cases:complaint", args=[self.complaint.pk]),
            "cases:complaint_uk_eml": reverse("cases:complaint_uk_eml", args=[self.complaint.pk]),
            "cases:complaint_evidence": reverse("cases:complaint_evidence", args=[self.complaint.pk]),
            "mail:upload": reverse("mail:upload", args=[subject]),
            "mail:discoveries": reverse("mail:discoveries", args=[subject]),
            "mail:unassigned": reverse("mail:unassigned", args=[subject]),
            "mail:assign": reverse("mail:assign", args=[subject, self.sender.pk]) + "?q=acme",
            "mail:connections": reverse("mail:connections", args=[subject]),
            "mail:connect": reverse("mail:connect", args=[subject, mailbox]),
            "mail:connection": reverse("mail:connection", args=[subject, mailbox]),
            "breaches:index": reverse("breaches:index"),
            "breaches:subject": reverse("breaches:subject", args=[subject]),
            "breaches:assign_list": reverse("breaches:assign_list"),
            "breaches:assign": reverse("breaches:assign", args=["SomeBreach"]) + "?q=broker",
            "stats:index": reverse("stats:index"),
            "llm:settings": reverse("llm:settings"),
            "llm:find_contact": reverse("llm:find_contact", args=["databroker"]),
            "legal:about": reverse("legal:about"),
            "legal:licence": reverse("legal:licence"),
            "legal:notices": reverse("legal:notices"),
            "legal:javascript": reverse("legal:javascript"),
            "backup:overview": reverse("backup:overview"),
        }

    def test_every_url_name_is_covered(self):
        covered = set(self.urls()) | POST_ONLY
        self.assertEqual(sorted(set(url_names()) - covered), [], "add new pages to this smoke test")

    def test_every_page_renders(self):
        for name, url in self.urls().items():
            with self.subTest(name=name):
                response = self.client.get(url)
                if name in REDIRECTS:
                    self.assertEqual(response.status_code, 302, f"{url}: {REDIRECTS[name]}")
                    continue
                self.assertEqual(response.status_code, 200, url)
                if response.get("Content-Type", "").startswith("text/html"):
                    html = response.content.decode()
                    self.assertNotIn('style="', html, url)
                    self.assertNotIn("<script>", html, url)
                    self.assertEqual(html.count('<link rel="stylesheet"'), html.count("stylesheet"), url)

    def test_batch_approval_takes_only_a_post(self):
        self.assertEqual(self.client.get(reverse("approve")).status_code, 405)

    def test_logged_in_pages_share_the_sidebar_and_drop_the_old_navs(self):
        for name in (
            "home",
            "subjects:detail",
            "cases:detail",
            "mail:discoveries",
            "organizations:detail",
            "stats:index",
        ):
            with self.subTest(name=name):
                html = self.client.get(self.urls()[name]).content.decode()
                self.assertIn('class="sidebar"', html)
                self.assertIn('class="topbar"', html)  # the same menu at phone width, in a <details>
                self.assertIn("<details>", html)
                self.assertIn("+ Add a Subject", html)
                for old in ("cases-nav", "mail-nav", "org-nav", "breach-nav", "stats-nav"):
                    self.assertNotIn(old, html)
                # Stylesheets only in <head>.
                head, body = html.split("</head>", 1)
                self.assertNotIn("<link", body)

    def test_brokers_are_marked(self):
        for name in ("subjects:detail", "cases:list", "cases:detail", "organizations:detail", "stats:index", "home"):
            with self.subTest(name=name):
                self.assertContains(self.client.get(self.urls()[name]), "tag-broker")


class SidebarTests(HouseholdMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.build()
        login(self)

    def test_counts(self):
        counts = household.needs_you_counts()
        # Alex: the awaiting draft, the matched reply. Sam: the overdue Case, the unmatched reply.
        self.assertEqual(counts[self.subject.pk], 2)
        self.assertEqual(counts[self.other.pk], 2)
        sidebar = household.sidebar()
        self.assertEqual(sidebar.needs_you, 4)
        self.assertEqual([s.name for s in sidebar.subjects], ["Alex Example", "Sam Example"])

    def test_sidebar_in_the_page(self):
        html = self.client.get(reverse("settings")).content.decode()
        nav = html.split('<aside class="sidebar">', 1)[1].split("</aside>", 1)[0]
        self.assertRegex(nav, r"Needs you\s*<span class=\"count\">4<")
        self.assertRegex(nav, r"Alex Example\s*<span class=\"count\">2<")
        self.assertRegex(nav, r"Sam Example\s*<span class=\"count\">2<")
        self.assertIn('href="/settings/" aria-current="page"', nav)

    def test_counts_cost_a_few_queries(self):
        with self.assertNumQueries(4):  # three counts and the Subjects
            household.sidebar()

    def test_no_sidebar_when_logged_out(self):
        self.client.logout()
        html = self.client.get(reverse("legal:about")).content.decode()
        self.assertNotIn('class="sidebar"', html)


class NeedsYouTests(HouseholdMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.build()
        login(self)

    def test_lists_what_waits(self):
        response = self.client.get("/?view=table")
        draft = self.awaiting.pending_draft
        self.assertContains(response, "Drafts to approve")
        self.assertContains(response, draft.recipient)
        self.assertContains(response, "Alex Example sends it from alex@example.org")  # import-only: handed over
        self.assertContains(response, "Replies to confirm")
        self.assertContains(response, "Who is this?")  # the unmatched reply
        self.assertContains(response, "Overdue or bounced")
        self.assertContains(response, "Quiet AG")
        self.assertContains(response, "Contact changes to review")
        self.assertContains(response, "1 Organization to look at")  # the discovery from the finished import
        self.assertNotContains(response, "Nothing needs you right now")

    def test_calm_when_nothing_waits(self):
        Case.objects.all().delete()
        Reply.objects.all().delete()
        PendingContactChange.objects.all().delete()
        Discovery.objects.all().delete()
        response = self.client.get("/?view=table")
        self.assertContains(response, "Nothing needs you right now.")

    def test_batch_summary_lists_every_recipient_then_approves_each(self):
        second = services.open_case(self.other, self.broker, on=DAY0)
        drafts = [self.awaiting.pending_draft, second.pending_draft]
        summary = self.client.post("/approve/", {"draft": [d.pk for d in drafts]})
        self.assertEqual(summary.status_code, 200)
        for draft in drafts:
            self.assertContains(summary, draft.recipient)
            self.assertContains(summary, f'name="draft" value="{draft.pk}"')
        self.assertContains(summary, "Approve all 2")
        self.assertEqual(Draft.objects.filter(status=Draft.Status.AWAITING_APPROVAL).count(), 2)  # nothing yet

        response = self.client.post("/approve/", {"draft": [d.pk for d in drafts], "confirm": "yes"}, follow=True)
        for draft in drafts:
            draft.refresh_from_db()
            self.assertEqual(draft.status, Draft.Status.HANDED_OVER)
        self.assertContains(response, "approved, handed over to the Subject")

    def test_batch_reports_each_draft_that_cannot_be_approved(self):
        good = self.awaiting.pending_draft
        bad = self.handed_draft  # already approved
        response = self.client.post("/approve/", {"draft": [good.pk, bad.pk], "confirm": "yes"}, follow=True)
        good.refresh_from_db()
        self.assertEqual(good.status, Draft.Status.HANDED_OVER)
        self.assertContains(response, f"{bad.case.reference} ({bad.case.organization.name}): not approved.")

    def test_batch_without_drafts(self):
        response = self.client.post("/approve/", {}, follow=True)
        self.assertContains(response, "Tick the drafts to approve first.")


class BoardTests(HouseholdMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.build()
        login(self)

    def test_table_by_default(self):
        response = self.client.get("/")
        self.assertNotContains(response, 'class="board"')
        self.assertNotIn(household.VIEW_COOKIE, response.cookies)

    def test_board_is_chosen_by_link_and_remembered_by_cookie(self):
        response = self.client.get("/?view=board")
        self.assertContains(response, 'class="board"')
        cookie = response.cookies[household.VIEW_COOKIE]
        self.assertEqual(cookie.value, "board")
        self.assertTrue(cookie["httponly"])
        # The browser sends it back: the board stays, on "Needs you" and on the Subject page.
        self.assertContains(self.client.get("/"), 'class="board"')
        self.assertContains(self.client.get(f"/subjects/{self.subject.pk}/"), 'class="board"')
        # And back to the table.
        response = self.client.get(f"/subjects/{self.subject.pk}/?view=table")
        self.assertNotContains(response, 'class="board"')
        self.assertEqual(response.cookies[household.VIEW_COOKIE].value, "table")
        self.assertNotContains(self.client.get("/"), 'class="board"')

    def test_columns_by_state(self):
        html = self.client.get("/?view=board").content.decode()
        for heading in ("Found", "Needs you", "With the Subject", "Waiting", "Resting", "Closed"):
            self.assertIn(f">{heading} <span", html)

        def column(key):
            return html.split(f'id="col-{key}"', 1)[1].split("</section>", 1)[0]

        self.assertIn("ACME Ltd", column("you"))  # awaiting approval
        self.assertIn("Quiet AG", column("you"))  # overdue
        self.assertIn("Data Broker GmbH", column("you"))  # paused, but a reply waits to be confirmed
        self.assertIn("Refuser SA", column("subject"))  # Complaint draft: the Subject lodges it
        self.assertIn("Found Shop", column("found"))  # a new discovery, with Pursue
        self.assertIn("/pursue/", column("found"))
        # Read as lists by a screen reader.
        self.assertIn('<section class="board-col', html)
        self.assertIn("<ul>", column("waiting"))

    def test_subject_board_and_tabs(self):
        url = f"/subjects/{self.subject.pk}/"
        response = self.client.get(url, {"view": "board", "tab": "done"})
        self.assertNotContains(response, "ACME Ltd")
        response = self.client.get(url, {"view": "table", "tab": "needs"})
        self.assertContains(response, "ACME Ltd")
        self.assertNotContains(response, "Refuser SA")
        response = self.client.get(url, {"view": "table", "tab": "open"})
        self.assertContains(response, "Refuser SA")


class SubjectPageTests(HouseholdMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.build()
        login(self)

    def test_header_counts_and_links(self):
        response = self.client.get(f"/subjects/{self.subject.pk}/?view=table")
        html = response.content.decode()
        self.assertContains(response, "Import only")
        self.assertContains(response, "Import new export")
        found = re.findall(r'<a href="([^"]+)"><b>(\d+)</b><span>([^<]+)</span>', html)
        counts = {label: (int(number), href.replace("&amp;", "&")) for href, number, label in found}
        discoveries = f"/mail/subjects/{self.subject.pk}/discoveries/"
        self.assertEqual(counts["Organizations"], (4, discoveries))  # three Cases and one discovery
        self.assertEqual(counts["Brokers"], (1, discoveries + "?broker=yes"))
        self.assertEqual(counts["Need you"][0], 2)
        self.assertEqual(
            counts["Waiting"], (0, "/cases/?" + urlencode({"subject": self.subject.pk, "state": "waiting"}))
        )
        for link in ("unassigned/", "/breaches/subjects/", "#about", f"/subjects/{self.subject.pk}/delete/"):
            self.assertIn(link, html)
        self.assertContains(response, "Identifying details")
        self.assertContains(response, "Withdraw consent")

    def test_live_mailbox_offers_a_rescan(self):
        Mailbox.objects.filter(subject=self.subject).update(mode=Mailbox.Mode.LIVE)
        response = self.client.get(f"/subjects/{self.subject.pk}/")
        self.assertContains(response, "Live connection")
        self.assertContains(response, "Re-scan mailbox")

    def test_without_mail_offers_import_or_connection(self):
        response = self.client.get(f"/subjects/{self.other.pk}/")
        self.assertContains(response, "no mail imported yet")
        self.assertContains(response, "or connect a mailbox")


class FilterTests(HouseholdMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.build()
        login(self)

    def references(self, **query):
        html = self.client.get("/cases/", query).content.decode()
        return set(re.findall(r"<code>(U-\w+)</code>", html))

    def test_case_list_filters(self):
        broker, refused = self.paused.reference, self.complaint.reference
        self.assertEqual(self.references(broker="yes"), {broker})
        self.assertNotIn(broker, self.references(broker="no"))
        self.assertEqual(self.references(organization="databroker"), {broker})
        self.assertEqual(self.references(organization=str(self.broker.pk)), {broker})
        self.assertEqual(self.references(organization="nobody"), set())
        self.assertEqual(self.references(result="refused"), {refused})
        self.assertEqual(self.references(result="refused", subject=self.other.pk), set())

    def test_result_filter_removed_and_suppression(self):
        case = services.open_case(self.other, self.broker, direct_removal=True, on=DAY0)
        send(case, DAY0)
        services.record_outcome(case, "removed", on=DAY0 + timedelta(days=3), suppression_confirmed=True)
        plain = services.open_case(self.other, self.refuser, direct_removal=True, on=DAY0)
        send(plain, DAY0)
        services.record_outcome(plain, "removed", on=DAY0 + timedelta(days=3), suppression_confirmed=False)
        self.assertEqual(self.references(result="removed"), {case.reference, plain.reference})
        self.assertEqual(self.references(result="removed_suppression"), {case.reference})
        self.assertEqual(self.references(result="nothing_held"), set())
        self.assertEqual(self.references(result="kept"), set())

    def test_discovery_filters(self):
        Discovery.objects.create(subject=self.subject, organization=self.broker, evidence=scanner.BULK)
        url = f"/mail/subjects/{self.subject.pk}/discoveries/"
        self.assertContains(self.client.get(url, {"broker": "yes"}), "Data Broker GmbH")
        self.assertNotContains(self.client.get(url, {"broker": "yes"}), "Found Shop")
        self.assertContains(self.client.get(url, {"broker": "no"}), "Found Shop")
        self.assertContains(self.client.get(url, {"evidence": scanner.BULK}), "Data Broker GmbH")
        self.assertNotContains(self.client.get(url, {"evidence": scanner.BULK}), "Found Shop")
        self.assertContains(self.client.get(url, {"evidence": "nonsense"}), "Found Shop")

    def test_statistics_link_to_the_exact_filters(self):
        html = self.client.get("/statistics/", {"subject": self.subject.pk}).content.decode()
        pk = self.subject.pk
        self.assertIn(f'href="/cases/?subject={pk}&amp;result=refused"', html)
        self.assertIn(f'href="/cases/?subject={pk}&amp;result=removed_suppression"', html)
        self.assertIn(f'href="/mail/subjects/{pk}/discoveries/?evidence=account"', html)
        self.assertIn(f'href="/mail/subjects/{pk}/discoveries/?broker=yes"', html)
        self.assertIn('href="/cases/?organization=databroker"', html)


class FirstRunTests(DataDirMixin, TestCase):
    def test_setup_then_subject_then_consent_then_import_then_discoveries(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/setup/", fetch_redirect_response=False)
        response = self.client.post("/setup/", {"username": "op", "password1": PASSWORD, "password2": PASSWORD})
        self.assertRedirects(response, "/subjects/add/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/subjects/add/"), "Add your first Subject")
        home = self.client.get("/")
        self.assertContains(home, "First steps")
        self.assertContains(home, "Add your first Subject")

        response = self.client.post(
            "/subjects/add/", {"name": "Robin", "country": "DE", "email": "robin@example.org", "year_of_birth": ""}
        )
        subject = Subject.objects.get()
        self.assertRedirects(response, f"/subjects/{subject.pk}/consent/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), f"Record {subject.name}")

        response = self.client.post(f"/subjects/{subject.pk}/consent/", {"given_by": "subject", "confirm": "on"})
        self.assertRedirects(response, f"/mail/subjects/{subject.pk}/import/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), "Import their mail")

        with mock.patch.object(importer, "RUN_IN_BACKGROUND", False):
            response = self.client.post(f"/mail/subjects/{subject.pk}/import/", {"file": fixture_upload()})
        self.assertRedirects(response, f"/mail/subjects/{subject.pk}/discoveries/", fetch_redirect_response=False)
        self.assertNotContains(self.client.get("/"), "First steps")

    def test_consent_with_mail_already_imported_goes_back_to_the_subject(self):
        login(self)
        subject = Subject.objects.create(name="Robin", country="DE")
        ImportRun.objects.create(subject=subject, finished_at=timezone.now())
        response = self.client.post(f"/subjects/{subject.pk}/consent/", {"given_by": "subject", "confirm": "on"})
        self.assertRedirects(response, f"/subjects/{subject.pk}/", fetch_redirect_response=False)

    def test_settings_page_links(self):
        login(self)
        response = self.client.get("/settings/")
        for target in ("/organizations/lists/", "/llm/", "/backup/", "/about/"):
            self.assertContains(response, f'href="{target}"')
