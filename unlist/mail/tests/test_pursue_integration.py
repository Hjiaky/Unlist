# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Discovery's "pursue" against the real Case lifecycle (no mocks)."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from unlist.cases.models import Case, Draft
from unlist.cases.tests.helpers import make_organization, make_subject
from unlist.mail import services
from unlist.mail.models import Discovery


class PursueOpensARealCaseTests(TestCase):
    def discovery(self, subject, organization, evidence="transaction"):
        now = timezone.now()
        return Discovery.objects.create(
            subject=subject,
            organization=organization,
            first_seen=now - timedelta(days=400),
            last_seen=now,
            email_count=12,
            evidence=evidence,
        )

    def test_pursue_opens_a_case_with_an_access_request_awaiting_approval(self):
        subject = make_subject()
        organization = make_organization()
        discovery = self.discovery(subject, organization)

        case = services.pursue(discovery)

        self.assertEqual(Case.objects.get().pk, case.pk)
        draft = case.drafts.get()
        self.assertEqual(draft.kind, "access_request")
        self.assertEqual(draft.status, Draft.Status.AWAITING_APPROVAL)
        self.assertEqual(draft.recipient, "privacy@acme.example")
        self.assertIn(case.reference, draft.subject_line)
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, Discovery.Status.PURSUED)
        self.assertIn(organization.pk, services.case_organization_ids(subject))

    def test_pursue_without_consent_is_refused_and_nothing_is_drafted(self):
        subject = make_subject(consent=False)
        discovery = self.discovery(subject, make_organization())
        with self.assertRaises(services.PursueError):
            services.pursue(discovery)
        self.assertFalse(Case.objects.exists())
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, Discovery.Status.NEW)

    def test_pursue_all_skips_organizations_that_already_have_a_case(self):
        subject = make_subject()
        first = make_organization("first", "First GmbH", email="privacy@first.example")
        second = make_organization("second", "Second AG", email="privacy@second.example")
        self.discovery(subject, first)
        self.discovery(subject, second)
        services.pursue(Discovery.objects.get(organization=first))

        pursued, errors = services.pursue_all_with_account_evidence(subject)

        self.assertEqual([d.organization for d in pursued], [second])
        self.assertEqual(errors, [])
        self.assertEqual(Case.objects.count(), 2)
