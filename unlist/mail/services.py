# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Operator actions on discovery results: pursue, ignore, assign a sender to an Organization."""

import logging

from django.apps import apps
from django.core.exceptions import FieldError
from django.db import transaction

from unlist.mail import scanner
from unlist.mail.importer import add_to_discovery, tally_of
from unlist.mail.models import Discovery, UnassignedSender
from unlist.organizations import merge
from unlist.organizations import services as organization_services

log = logging.getLogger("unlist.mail")


class PursueError(Exception):
    pass


class AssignError(Exception):
    pass


def case_organization_ids(subject):
    """Pks of the Organizations the Subject already has a Case with, as far as the Cases app tells."""
    try:
        case_model = apps.get_model("cases", "Case")
        return set(case_model.objects.filter(subject=subject).values_list("organization_id", flat=True))
    except (LookupError, FieldError):
        return set()


def pursue(discovery):
    """Open a Case for the discovery's Subject and Organization; mark it pursued. Raises PursueError."""
    try:
        from unlist.cases.services import open_case
    except ImportError as error:
        raise PursueError("Cases cannot be opened yet in this version.") from error
    try:
        with transaction.atomic():
            case = open_case(discovery.subject, discovery.organization)
    except Exception as error:  # open_case refuses with its own errors (no consent, no confirmed contact)
        raise PursueError(f"{discovery.organization.name}: {error}") from error
    discovery.status = Discovery.Status.PURSUED
    discovery.save(update_fields=["status", "updated_at"])
    return case


def pursuable_with_account_evidence(subject):
    """New discoveries with account evidence or better and no Case yet."""
    with_case = case_organization_ids(subject)
    return [
        discovery
        for discovery in subject.discoveries.filter(status=Discovery.Status.NEW, evidence__in=scanner.ACCOUNT_OR_BETTER)
        .select_related("organization", "subject")
        .order_by("organization__name")
        if discovery.organization_id not in with_case
    ]


def pursue_all_with_account_evidence(subject):
    """Pursue every new discovery with account evidence or better. Returns (pursued, [error messages])."""
    pursued, errors = [], []
    for discovery in pursuable_with_account_evidence(subject):
        try:
            pursue(discovery)
        except PursueError as error:
            errors.append(str(error))
        else:
            pursued.append(discovery)
    return pursued, errors


def ignore(discovery):
    discovery.status = Discovery.Status.IGNORED
    discovery.save(update_fields=["status", "updated_at"])


def unignore(discovery):
    discovery.status = Discovery.Status.NEW
    discovery.save(update_fields=["status", "updated_at"])


def ignore_sender(sender):
    sender.status = UnassignedSender.Status.IGNORED
    sender.save(update_fields=["status", "updated_at"])


def unignore_sender(sender):
    sender.status = UnassignedSender.Status.OPEN
    sender.save(update_fields=["status", "updated_at"])


@transaction.atomic
def assign_sender(sender, organization):
    """Assign a sender to an Organization and move its counts into a Discovery. Raises AssignError.

    An unknown domain is stored as a local domain override of the Organization, so later
    scans (for every Subject) map it on their own; other Subjects' open senders on that
    domain are moved at once. A shared mail or platform domain can never belong to one
    Organization, so for it only this sender (this display name, this Subject) is assigned.
    """
    if organization.obsolete:
        raise AssignError(f"{organization.name} is obsolete; choose the Organization it moved to.")
    senders = [sender]
    if not sender.ambiguous:
        domains = sorted(set(organization.domains) | {sender.domain})
        try:
            value = organization_services.parse_override(merge.DOMAINS, "\n".join(domains))
        except organization_services.OverrideError as error:
            raise AssignError(str(error)) from error
        organization_services.set_override(
            organization.slug, merge.DOMAINS, value, note=f"{sender.domain} assigned from mail discovery"
        )
        senders += list(
            UnassignedSender.objects.filter(
                domain=sender.domain, ambiguous=False, status=UnassignedSender.Status.OPEN
            ).exclude(pk=sender.pk)
        )
    for item in senders:
        add_to_discovery(item.subject, organization, tally_of(item))
        item.status, item.organization = UnassignedSender.Status.ASSIGNED, organization
        item.save(update_fields=["status", "organization", "updated_at"])
