# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""What the Cases app plugs into other apps' hooks. Registered from ``CasesConfig.ready()``."""

from unlist.backup import hooks as backup_hooks
from unlist.cases import storage
from unlist.organizations import hooks as organization_hooks
from unlist.subjects import consent, deletion

CONSENT_WITHDRAWN = "consent withdrawn"


def organization_has_case(slug: str) -> bool:
    """``organizations.hooks.has_case``: True when any Case refers to the Organization with this slug."""
    from unlist.cases.models import Case

    return Case.objects.filter(organization__slug=slug).exists()


def stop_cases_on_withdrawal(subject, withdrawn_consent) -> None:
    """``subjects.consent.on_withdrawn``: close every Case of the Subject that is not closed yet.

    Resting Cases close too: a re-check would act in the Subject's name. Pending drafts are discarded.
    """
    from unlist.cases import services
    from unlist.cases.lifecycle import State

    for case in subject.cases.exclude(state=State.CLOSED):
        services.stop(case, reason=CONSENT_WITHDRAWN)


def register() -> None:
    from unlist.cases import complaints, services

    for registry, hook in (
        (services.complaint_drafters, complaints.on_complaint_drafted),
        (organization_hooks.has_case, organization_has_case),
        (consent.on_withdrawn, stop_cases_on_withdrawal),
        (deletion.before_delete, storage.delete_subject_attachments),
        (backup_hooks.integrity_checks, storage.integrity_check),
    ):
        if hook not in registry:
            registry.append(hook)
