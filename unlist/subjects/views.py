# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from unlist.core import household
from unlist.subjects.consent import CONSENT_SCOPE, record_consent, withdraw_consent
from unlist.subjects.deletion import delete_subject
from unlist.subjects.forms import ConsentForm, IdentifyingDetailForm, MailboxForm, SubjectForm
from unlist.subjects.models import Subject

# The Subject page's tabs: label, and which board columns each shows (None: all).
TABS = {
    "all": ("All", None),
    "needs": ("Needs you", {"you"}),
    "open": ("Open", {"found", "you", "subject", "waiting"}),
    "done": ("Done", {"resting", "closed"}),
}


@login_required
def subject_list(request):
    return render(request, "subjects/list.html", {"subjects": Subject.objects.all()})


@login_required
def subject_add(request):
    form = SubjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        subject = form.save()
        # Next step of the first run (spec section 13): consent, then mail.
        return redirect("subjects:consent", pk=subject.pk)
    return render(request, "subjects/add.html", {"form": form, "first": not Subject.objects.exists()})


def _query(**params) -> str:
    return "?" + urlencode(params)


@login_required
def subject_detail(request, pk):
    """The Subject's hub: their mail, five counts, and their Cases as a table or a board."""
    from unlist.cases.models import Case
    from unlist.mail.models import Discovery, UnassignedSender

    subject = get_object_or_404(Subject, pk=pk)
    view, remember = household.chosen_view(request)
    tab = request.GET.get("tab", "all")
    if tab not in TABS:
        tab = "all"

    cases = Case.objects.filter(subject=subject).select_related("organization").order_by("organization__name")
    drafts = household.drafts_awaiting(subject)
    rows = household.case_rows(cases, household.reply_case_ids(subject), drafts)
    columns = TABS[tab][1]
    shown = [row for row in rows if columns is None or row["column"] in columns]
    found = household.new_discoveries(subject) if columns is None or "found" in columns else []

    # Every Organization known to hold this Subject's data: those with a Case and those found in the mail.
    organizations = {row["case"].organization for row in rows}
    organizations.update(
        discovery.organization
        for discovery in Discovery.objects.filter(subject=subject)
        .exclude(status=Discovery.Status.IGNORED)
        .select_related("organization")
    )
    discoveries_url = reverse("mail:discoveries", args=[pk])
    cases_url = reverse("cases:list")
    here = reverse("subjects:detail", args=[pk])
    counts = [
        ("Organizations", len(organizations), discoveries_url),
        ("Brokers", sum(o.broker for o in organizations), discoveries_url + _query(broker="yes")),
        ("Need you", sum(row["column"] == "you" for row in rows), here + _query(tab="needs")),
        ("Waiting", sum(row["column"] == "waiting" for row in rows), cases_url + _query(subject=pk, state="waiting")),
        ("Done", sum(row["column"] in ("resting", "closed") for row in rows), here + _query(tab="done")),
    ]
    context = {
        "subject": subject,
        "mail": household.mail_status(subject),
        "counts": counts,
        "tabs": [(key, label) for key, (label, _) in TABS.items()],
        "tab": tab,
        "view": view,
        "toggle_query": f"tab={tab}&" if tab != "all" else "",
        "rows": shown,
        "found": found,
        "has_drafts": bool(drafts),
        "unassigned": UnassignedSender.objects.filter(subject=subject, status=UnassignedSender.Status.OPEN).count(),
        "mailboxes": subject.mailboxes.all(),
        "details": subject.details.all(),
        "consent": subject.consents.filter(withdrawn_at__isnull=True).first(),
        "last_withdrawn": subject.consents.filter(withdrawn_at__isnull=False).order_by("-withdrawn_at").first(),
    }
    if view == "board":
        context["columns"] = household.board(
            shown,
            found,
            found_total=len(found),
            found_url=discoveries_url,
            more_urls={
                "resting": cases_url + _query(subject=pk, state="resting"),
                "closed": cases_url + _query(subject=pk, state="closed"),
            },
        )
    response = render(request, "subjects/detail.html", context)
    return household.remember_view(response, view) if remember else response


@login_required
def consent_record(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if subject.has_active_consent():
        return redirect("subjects:detail", pk=pk)
    form = ConsentForm(request.POST or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        record_consent(subject, form.cleaned_data["given_by"])
        if household.mail_status(subject)["last"] is None:
            return redirect("mail:upload", pk=pk)  # first run: import the mail next
        return redirect("subjects:detail", pk=pk)
    return render(request, "subjects/consent.html", {"subject": subject, "form": form, "scope": CONSENT_SCOPE})


@login_required
@require_POST
def consent_withdraw(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    withdraw_consent(subject)
    return redirect("subjects:detail", pk=pk)


@login_required
def detail_add(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = IdentifyingDetailForm(request.POST or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("subjects:detail", pk=pk)
    return render(request, "subjects/detail_add.html", {"subject": subject, "form": form})


@login_required
@require_POST
def detail_remove(request, pk, detail_pk):
    subject = get_object_or_404(Subject, pk=pk)
    get_object_or_404(subject.details, pk=detail_pk).delete()
    return redirect("subjects:detail", pk=pk)


@login_required
def mailbox_add(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = MailboxForm(request.POST or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("subjects:detail", pk=pk)
    return render(request, "subjects/mailbox_add.html", {"subject": subject, "form": form})


@login_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        delete_subject(subject)
        return redirect("subjects:list")
    return render(request, "subjects/delete.html", {"subject": subject})
