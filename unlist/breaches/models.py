# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The Have I Been Pwned breach catalogue (spec section 10). Breach data is CC BY 4.0."""

import html

from django.db import models
from django.utils.html import strip_tags


class Breach(models.Model):
    """One breach of the free Have I Been Pwned catalogue. Never says anything about a Subject."""

    name = models.CharField(max_length=200, unique=True, help_text="HIBP's stable key.")
    title = models.CharField(max_length=300)
    domain = models.CharField(max_length=253, blank=True, help_text="The breached site's primary domain; often empty.")
    breach_date = models.DateField(null=True, blank=True)
    added_date = models.DateTimeField(null=True, blank=True)
    data_classes = models.JSONField(default=list, blank=True)
    is_verified = models.BooleanField(default=False)
    is_spam_list = models.BooleanField(default=False)
    is_malware = models.BooleanField(default=False)
    is_fabricated = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    attribution = models.CharField(max_length=500, blank=True, help_text="HIBP's own credit for this breach.")
    description = models.TextField(blank=True, help_text="Raw text from HIBP; may contain HTML. Show it as text only.")

    class Meta:
        ordering = ["title", "name"]

    def __str__(self):
        return self.title or self.name

    @property
    def plain_description(self):
        """The description as plain text: tags removed, entities decoded. Templates escape it again."""
        return html.unescape(strip_tags(self.description))

    @property
    def excluded(self):
        """Spam lists, malware and fabricated entries are never matched to an Organization."""
        return self.is_spam_list or self.is_malware or self.is_fabricated


class BreachAssignment(models.Model):
    """The Operator's own link from a breach (by name) to an Organization, for breaches without a domain."""

    breach_name = models.CharField(max_length=200, unique=True)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["breach_name"]

    def __str__(self):
        return f"{self.breach_name} -> {self.organization}"


class BreachCatalogue(models.Model):
    """Where the loaded breaches came from. One row (pk 1)."""

    source = models.CharField(max_length=500)
    fetched_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
    bundled = models.BooleanField(default=True, help_text="False once the Operator pressed Update breach list.")
