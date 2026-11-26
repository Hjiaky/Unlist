# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.db import models
from django.db.models import Q

from unlist.organizations.merge import CONTACT_FIELDS, LOCAL, OVERRIDABLE


class OrganizationList(models.Model):
    """A subscribed Organization List. Lower `position` is higher priority."""

    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, blank=True, help_text="Blank for a list bundled with Unlist.")
    position = models.PositiveIntegerField(default=0)
    licence = models.CharField(max_length=100, blank=True)
    homepage = models.URLField(max_length=500, blank=True)
    version = models.CharField(max_length=100, blank=True)
    date = models.DateField(null=True, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    bundled = models.BooleanField(default=False)
    bundled_file = models.CharField(max_length=100, blank=True)
    notes = models.JSONField(default=list, blank=True, help_text="Records skipped at the last load, and why.")
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name


class ListRecord(models.Model):
    """One record of one list, as loaded, so the merge can be recomputed at any time."""

    organization_list = models.ForeignKey(OrganizationList, on_delete=models.CASCADE, related_name="records")
    slug = models.CharField(max_length=200)
    data = models.JSONField()
    obsolete = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization_list", "slug"], name="unique_record_per_list")]


class Organization(models.Model):
    """The merged view of an Organization over all enabled lists and local overrides."""

    QUALITY_CHOICES = [
        ("tested", "tested"),
        ("verified", "verified"),
        ("imported", "imported"),
        ("scraped", "scraped"),
        ("local", "local"),
    ]
    CHANNEL_CHOICES = [("email", "email"), ("letter", "letter"), ("webform", "web form")]

    slug = models.CharField(max_length=200, unique=True)
    name = models.CharField(max_length=300)
    runs = models.JSONField(default=list, blank=True)
    domains = models.JSONField(default=list, blank=True)
    # Contacts
    email = models.CharField(max_length=300, blank=True)
    address = models.TextField(blank=True)
    webform = models.CharField(max_length=1000, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    web = models.CharField(max_length=1000, blank=True)
    preferred_channel = models.CharField(max_length=20, blank=True, choices=CHANNEL_CHOICES)
    # Quirks
    required_elements = models.JSONField(default=list, blank=True)
    needs_id_document = models.BooleanField(default=False)
    request_language = models.CharField(max_length=10, blank=True)
    comments = models.JSONField(default=list, blank=True)
    notes = models.JSONField(default=list, blank=True)
    # Scope
    relevant_countries = models.JSONField(default=list, blank=True)
    supervisory_authority = models.CharField(max_length=100, blank=True)
    categories = models.JSONField(default=list, blank=True)
    broker = models.BooleanField(default=False)
    recheck_default = models.PositiveIntegerField(null=True, blank=True, help_text="Days; empty uses the default.")
    last_checked = models.DateField(null=True, blank=True)
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default="verified")
    sources = models.JSONField(default=list, blank=True)
    # Merge bookkeeping
    field_sources = models.JSONField(default=dict, blank=True)
    conflicts = models.JSONField(default=dict, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    obsolete = models.BooleanField(default=False)
    redirect_to = models.CharField(max_length=200, blank=True)
    listed = models.BooleanField(default=True, help_text="False when no list has it any more but a Case keeps it.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "slug"]

    def __str__(self):
        return self.name

    @property
    def is_stub(self):
        return self.quality == "local"

    @property
    def has_contact(self):
        return bool(self.email or self.address or self.webform)

    @property
    def contact_confirmed(self):
        """Scraped records and local stubs need the Operator to confirm a contact first (spec section 4)."""
        if self.quality not in ("scraped", "local"):
            return True
        return any(self.field_sources.get(name) == LOCAL for name in CONTACT_FIELDS) and self.has_contact


class Domain(models.Model):
    """A domain claimed for an Organization by one source: a list, or a local override (source empty)."""

    domain = models.CharField(max_length=253, db_index=True)
    source = models.ForeignKey(OrganizationList, null=True, blank=True, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="domain_claims")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["domain", "source"], name="unique_domain_per_list"),
            models.UniqueConstraint(
                fields=["domain", "organization"], condition=Q(source__isnull=True), name="unique_local_domain"
            ),
        ]


class LocalOverride(models.Model):
    """The Operator's own value for one field of one Organization; beats every list."""

    organization_slug = models.CharField(max_length=200, db_index=True)
    field = models.CharField(max_length=50, choices=[(name, name) for name in OVERRIDABLE])
    value = models.JSONField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization_slug", "field"]
        constraints = [models.UniqueConstraint(fields=["organization_slug", "field"], name="unique_override")]


class PendingContactChange(models.Model):
    """A list update that would change the contact of an Organization with a Case, held for review."""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="pending_contact")
    old = models.JSONField()
    new = models.JSONField()
    new_sources = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def rows(self):
        return [(name, self.old.get(name, ""), self.new.get(name, "")) for name in CONTACT_FIELDS]


class SupervisoryAuthority(models.Model):
    slug = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=300)
    countries = models.JSONField(default=list)
    address = models.TextField(blank=True)
    email = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    webform = models.CharField(max_length=1000, blank=True)
    web = models.CharField(max_length=1000, blank=True)
    complaint_language = models.CharField(max_length=10, blank=True)
    preferred_channel = models.CharField(max_length=20, blank=True)
    sources = models.JSONField(default=list, blank=True)
    comments = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
