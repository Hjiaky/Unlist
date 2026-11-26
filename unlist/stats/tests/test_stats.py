# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The statistics dashboard (#55): figures, snapshots, chart and page."""

import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from unlist.cases import services
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.mail import scanner
from unlist.mail.models import Discovery
from unlist.stats import charts, figures, snapshots
from unlist.stats.models import MonthlySnapshot


def days(n):
    return DAY0 + timedelta(days=n)


def answered(subject, organization, outcome, on, *, sent_on=DAY0, **details):
    case = services.open_case(subject, organization, on=sent_on)
    send(case, sent_on)
    services.record_outcome(case, outcome, on=on, **details)
    case.refresh_from_db()
    return case


class FixtureMixin:
    """One Subject with a Case or a Discovery in every standing."""

    def build(self):
        self.subject = make_subject()
        self.broker = make_organization("broker", "Data Broker", broker=True)
        self.nothing = make_organization("nothing", "Nothing Ltd")
        self.listed = make_organization("listed", "Listed Ltd")
        self.kept = make_organization("kept", "Kept Ltd")
        self.refused = make_organization("refused", "Refused Ltd")
        self.account = make_organization("account", "Account Ltd")
        self.bulk = make_organization("bulk", "Bulk Ltd")
        self.ignored = make_organization("ignored", "Ignored Ltd")

        # Removed, with a Suppression Record confirmed.
        case = answered(self.subject, self.broker, "listing_found", days(12))
        services.request_removal(case, on=days(12))
        send(case, days(12))
        services.record_outcome(case, "removed", on=days(32), suppression_confirmed=True)
        # Nothing held.
        answered(self.subject, self.nothing, "nothing_held", days(7))
        # Listing found, undecided.
        answered(self.subject, self.listed, "listing_found", days(5))
        # Listing found, kept by choice.
        case = answered(self.subject, self.kept, "listing_found", days(5))
        services.keep_listing(case, on=days(6))
        # Refused.
        answered(self.subject, self.refused, "refused", days(9), exception="Art. 17(3)")

        def discover(organization, evidence, status=Discovery.Status.NEW):
            Discovery.objects.create(subject=self.subject, organization=organization, evidence=evidence, status=status)

        discover(self.broker, scanner.ACCOUNT)
        discover(self.account, scanner.ACCOUNT)
        discover(self.bulk, scanner.BULK)
        discover(self.ignored, scanner.TRANSACTION, Discovery.Status.IGNORED)
        discover(self.nothing, scanner.ORDER_MARKUP)
        discover(self.refused, scanner.ACCOUNT)


class FigureTests(FixtureMixin, TestCase):
    def setUp(self):
        self.build()

    def test_evidence_and_brokers(self):
        found = figures.compute(self.subject.pk)
        self.assertEqual(found.discoveries, 6)
        self.assertEqual(found.evidence[scanner.ACCOUNT], 3)
        self.assertEqual(found.evidence[scanner.BULK], 1)
        self.assertEqual(found.evidence[scanner.TRANSACTION], 1)
        self.assertEqual(found.evidence[scanner.ORDER_MARKUP], 1)
        self.assertEqual(found.brokers, 1)

    def test_cases_by_state(self):
        found = figures.compute(self.subject.pk)
        self.assertEqual(found.cases, 5)
        self.assertEqual(found.cases_by_state["resting"], 1)  # the removed Broker
        self.assertEqual(found.cases_by_state["listing_found"], 1)
        self.assertEqual(found.cases_by_state["refused"], 1)
        self.assertEqual(found.cases_by_state["closed"], 2)  # nothing held, kept

    def test_outcomes(self):
        found = figures.compute(self.subject.pk)
        self.assertEqual(found.outcomes[figures.REMOVED], 1)
        self.assertEqual(found.removed_confirmed, 1)
        self.assertEqual(found.outcomes[figures.NOTHING_HELD], 1)
        self.assertEqual(found.outcomes[figures.REFUSED], 1)
        self.assertEqual(found.outcomes[figures.KEPT], 1)

    def test_removed_without_a_confirmed_suppression_record(self):
        subject = make_subject("Sam", "sam@example.org")
        case = answered(subject, make_organization("other", "Other Broker", broker=True), "listing_found", days(3))
        services.request_removal(case, on=days(3))
        send(case, days(3))
        services.record_outcome(case, "removed", on=days(20), suppression_confirmed=False)
        found = figures.compute(subject.pk)
        self.assertEqual((found.outcomes[figures.REMOVED], found.removed_confirmed), (1, 0))

    def test_holding_and_removed(self):
        found = figures.compute(self.subject.pk)
        # Holding: listed, kept (Listings), refused (account evidence), account (Discovery only).
        # Not holding: the removed Broker, nothing held (despite order markup), bulk mail, ignored.
        self.assertEqual(found.holding, 4)
        self.assertEqual(found.removed, 1)

    def test_a_listing_found_again_after_removal_counts_as_holding(self):
        case = figures.Case.objects.get(organization=self.broker)
        services.prepare_recheck(case, on=days(120))
        send(case, days(120))
        services.record_outcome(case, "listing_found", on=days(125))
        found = figures.compute(self.subject.pk)
        self.assertEqual((found.holding, found.removed), (5, 0))

    def test_household_is_the_sum_of_the_subjects(self):
        other = make_subject("Sam", "sam@example.org")
        answered(other, self.listed, "nothing_held", days(4))
        household = figures.compute(None)
        mine = figures.compute(self.subject.pk)
        theirs = figures.compute(other.pk)
        self.assertEqual(household.cases, mine.cases + theirs.cases)
        self.assertEqual(household.holding, mine.holding + theirs.holding)
        self.assertEqual(theirs.outcomes[figures.NOTHING_HELD], 1)
        self.assertEqual(theirs.holding, 0)

    def test_a_subject_with_nothing_has_empty_figures(self):
        other = make_subject("Sam", "sam@example.org")
        found = figures.compute(other.pk)
        self.assertEqual((found.cases, found.holding, found.removed, found.discoveries), (0, 0, 0, 0))


class OrganizationFigureTests(TestCase):
    def test_median_on_time_and_id_demands(self):
        organization = make_organization("slowpoke", "Slowpoke Ltd")
        for index, answer_day in enumerate((4, 10, 60)):
            subject = make_subject(f"Person {index}", f"p{index}@example.org")
            answered(subject, organization, "listing_found", days(answer_day))
        demanding = make_organization("demanding", "Demanding Ltd")
        subject = make_subject("Asker", "asker@example.org")
        case = services.open_case(subject, demanding, on=DAY0)
        send(case, DAY0)
        services.record_outcome(case, "id_or_details_asked", on=days(3))
        unasked = make_organization("unasked", "Never Opened Ltd")  # no Case: not listed

        rows = {row.organization.slug: row for row in figures.organization_figures()}
        self.assertNotIn(unasked.slug, rows)
        slow = rows["slowpoke"]
        self.assertEqual(slow.cases, 3)
        self.assertEqual(slow.median_days, 10)
        self.assertEqual((slow.on_time, slow.answered, slow.on_time_percent), (2, 3, 67))
        ask = rows["demanding"]
        self.assertEqual(ask.id_demands, 1)
        self.assertEqual(ask.median_days, 3)  # asking for ID is an answer

    def test_median_of_an_even_count_and_sorting_by_name(self):
        zed = make_organization("zed", "Zed Ltd")
        abe = make_organization("abe", "abe Ltd")
        for index, answer_day in enumerate((4, 7)):
            answered(make_subject(f"P{index}", f"q{index}@example.org"), zed, "nothing_held", days(answer_day))
        answered(make_subject("P9", "q9@example.org"), abe, "nothing_held", days(2))
        rows = figures.organization_figures()
        self.assertEqual([row.organization.slug for row in rows], ["abe", "zed"])
        self.assertEqual(rows[1].median_days, 5.5)

    def test_unanswered_and_bounced_requests_have_no_figures(self):
        subject = make_subject()
        organization = make_organization()
        case = services.open_case(subject, organization, on=DAY0)
        send(case, DAY0)
        (row,) = figures.organization_figures()
        self.assertEqual((row.cases, row.answered, row.median_days, row.on_time_percent), (1, 0, None, None))
        services.record_outcome(case, "bounce", on=days(1))
        (row,) = figures.organization_figures()
        self.assertEqual(row.answered, 0)

    def test_an_answer_after_a_reminder_is_late(self):
        subject = make_subject()
        organization = make_organization()
        case = services.open_case(subject, organization, on=DAY0)
        send(case, DAY0)
        services.mark_overdue_if_due(case, today=days(45))
        services.send_reminder(case, on=days(45))
        send(case, days(45))
        services.record_outcome(case, "nothing_held", on=days(50))
        (row,) = figures.organization_figures()
        self.assertEqual((row.answered, row.on_time, row.median_days), (1, 0, 50))


class SnapshotTests(FixtureMixin, TestCase):
    def setUp(self):
        self.build()
        self.today = date(2026, 11, 26)

    def test_record_writes_a_row_per_subject_and_the_household(self):
        self.assertTrue(snapshots.record_snapshots(self.today))
        mine = MonthlySnapshot.objects.get(subject=self.subject)
        household = MonthlySnapshot.objects.get(subject=None)
        self.assertEqual(mine.month, date(2026, 11, 1))
        self.assertEqual((mine.holding, mine.removed), (4, 1))
        self.assertEqual((household.holding, household.removed), (4, 1))
        self.assertEqual(mine.counts["brokers"], 1)
        self.assertEqual(mine.counts["outcomes"]["removed"], 1)

    def test_idempotent_within_a_day_and_rewritten_on_a_later_day(self):
        self.assertTrue(snapshots.record_snapshots(self.today))
        self.assertFalse(snapshots.record_snapshots(self.today))
        self.assertEqual(MonthlySnapshot.objects.count(), 2)

        # A later run the same month rewrites the same rows rather than adding new ones.
        MonthlySnapshot.objects.update(updated_at=timezone.now() - timedelta(days=1))
        answered(make_subject("Sam", "sam@example.org"), self.listed, "listing_found", days(3))
        self.assertTrue(snapshots.record_snapshots(self.today))
        self.assertEqual(MonthlySnapshot.objects.filter(subject=None).count(), 1)
        self.assertEqual(MonthlySnapshot.objects.get(subject=None).holding, 5)
        self.assertEqual(MonthlySnapshot.objects.count(), 3)

    def test_scheduler_job(self):
        from unlist.core import scheduler
        from unlist.stats import jobs

        self.assertIn(jobs.record_monthly_snapshot, scheduler.JOBS)
        now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
        self.assertIn("2026-11", jobs.record_monthly_snapshot(now))
        self.assertIsNone(jobs.record_monthly_snapshot(now))
        self.assertEqual(MonthlySnapshot.objects.count(), 2)

    def test_history_is_earlier_snapshots_plus_the_live_month(self):
        subject_id = self.subject.pk
        for month, holding, removed in ((date(2026, 9, 1), 2, 0), (date(2026, 10, 1), 3, 1)):
            MonthlySnapshot.objects.create(month=month, subject_id=subject_id, holding=holding, removed=removed)
        # A stale row for the current month and a household row must not leak in.
        MonthlySnapshot.objects.create(month=date(2026, 11, 1), subject_id=subject_id, holding=99, removed=99)
        MonthlySnapshot.objects.create(month=date(2026, 10, 1), subject=None, holding=50, removed=50)
        live = figures.compute(subject_id)
        self.assertEqual(
            snapshots.history(subject_id, live, self.today),
            [(date(2026, 9, 1), 2, 0), (date(2026, 10, 1), 3, 1), (date(2026, 11, 1), 4, 1)],
        )
        self.assertEqual(
            snapshots.history(None, live, self.today), [(date(2026, 10, 1), 50, 50), (date(2026, 11, 1), 4, 1)]
        )

    def test_deleting_a_subject_deletes_its_snapshots(self):
        snapshots.record_snapshots(self.today)
        self.subject.cases.all().delete()
        self.subject.delete()
        self.assertFalse(MonthlySnapshot.objects.filter(subject__isnull=False).exists())


class ChartTests(SimpleTestCase):
    def points(self, count):
        return [(date(2025 + (i // 12), i % 12 + 1, 1), i, i // 2) for i in range(count)]

    def test_well_formed_without_script_or_inline_style(self):
        for count in (1, 2, 7, 30):
            svg = charts.line_chart(self.points(count), uid="t", title="A & B <x>", description='Two "series" & more')
            root = ET.fromstring(svg)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertNotIn("<script", svg.lower())
            self.assertNotIn("style=", svg.lower())
            self.assertIn("A &amp; B &lt;x&gt;", svg)
            self.assertEqual(root.get("role"), "img")
            self.assertEqual(len(root.findall("{http://www.w3.org/2000/svg}title")), 1)
            self.assertEqual(len(root.findall("{http://www.w3.org/2000/svg}desc")), 1)

    def test_text_labels_carry_the_values(self):
        svg = charts.line_chart([(date(2026, 10, 1), 7, 3)], uid="t", title="T", description="D")
        texts = [element.text for element in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}text")]
        self.assertIn("Oct 2026", texts)
        self.assertIn("7", texts)
        self.assertIn("3", texts)
        self.assertIn("Holding data", texts)
        self.assertIn("Removed", texts)

    def test_axis_top(self):
        self.assertEqual([charts._nice_top(n) for n in (0, 4, 5, 9, 11, 40, 120)], [4, 4, 5, 10, 20, 50, 200])


class PageTests(FixtureMixin, TestCase):
    def setUp(self):
        self.build()
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)

    def test_needs_login(self):
        self.client.logout()
        self.assertEqual(self.client.get("/statistics/").status_code, 302)

    def test_household_and_subject_pages(self):
        for query in ({}, {"subject": self.subject.pk}, {"subject": "nonsense"}, {"subject": 9999}):
            response = self.client.get("/statistics/", query)
            self.assertEqual(response.status_code, 200, query)
            self.assertContains(response, "<svg")
            self.assertContains(response, "stats/stats.css")
        response = self.client.get("/statistics/", {"subject": self.subject.pk})
        self.assertContains(response, "Alex Example")
        self.assertContains(response, "Data Broker")

    def test_empty_instance(self):
        figures.Case.objects.all().delete()
        Discovery.objects.all().delete()
        self.subject.delete()
        response = self.client.get("/statistics/")
        self.assertContains(response, "No Subjects yet.")
        self.assertContains(response, "No Cases yet.")

    def test_every_number_is_a_link(self):
        for query in ({}, {"subject": self.subject.pk}):
            html = self.client.get("/statistics/", query).content.decode()
            main = html.split("<main", 1)[1].split("</main>", 1)[0]
            links = re.findall(r'<a class="stat" href="([^"]*)">([^<]*)</a>', main)
            self.assertGreater(len(links), 20)
            for target, text in links:
                self.assertTrue(target.startswith("/"), target)
                self.assertTrue(re.search(r"\d", text), text)
            # No digit is left outside a link, the chart or a form option.
            rest = re.sub(r'<a class="stat"[^>]*>[^<]*</a>', "", main)
            rest = re.sub(r"<svg.*?</svg>", "", rest, flags=re.S)
            rest = re.sub(r"<option.*?</option>", "", rest, flags=re.S)
            rest = re.sub(r"<[^>]+>", " ", rest)
            self.assertIsNone(re.search(r"\d", rest), re.search(r".{30}\d.{30}", rest))

    def test_links_use_the_case_list_filters(self):
        html = self.client.get("/statistics/", {"subject": self.subject.pk}).content.decode()
        self.assertIn(f'href="/cases/?subject={self.subject.pk}&amp;state=listing_found"', html)
        self.assertIn(f'href="/mail/subjects/{self.subject.pk}/discoveries/"', html)
        self.assertIn('href="/organizations/o/broker/"', html)
        household = self.client.get("/statistics/").content.decode()
        self.assertIn('href="/cases/?state=listing_found"', household)

    def test_the_page_shows_the_figures(self):
        html = self.client.get("/statistics/", {"subject": self.subject.pk}).content.decode()
        self.assertIn("Holding data now", html)
        self.assertRegex(html, r'Holding data now: <a class="stat" href="[^"]*">4</a>')
        self.assertRegex(html, r'Removed now: <a class="stat" href="[^"]*">1</a>')
        self.assertIn("Suppression Record confirmed", html)
        self.assertNotIn("style=", html.split("<body", 1)[1])
        self.assertNotIn("<script", html.split("<body", 1)[1].lower().replace("<script src", ""))
