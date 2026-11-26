# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.db import models
from django.utils import timezone

ADULT_AGE = 18
OWN_INVOLVEMENT_AGE = 12


class Subject(models.Model):
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=2, help_text="ISO 3166-1 alpha-2 code of the country of residence.")
    year_of_birth = models.PositiveSmallIntegerField(null=True, blank=True)
    parental_responsibility = models.CharField(
        max_length=200, blank=True, help_text="Who holds parental responsibility, for a child."
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def age(self, today=None):
        """Age in years from the year of birth alone (this year minus the year of birth), or None."""
        if self.year_of_birth is None:
            return None
        return (today or timezone.localdate()).year - self.year_of_birth

    @property
    def is_child(self):
        age = self.age()
        return age is not None and age < ADULT_AGE

    @property
    def needs_own_involvement(self):
        return self.is_child and self.age() >= OWN_INVOLVEMENT_AGE

    def has_active_consent(self):
        return self.consents.filter(withdrawn_at__isnull=True).exists()


class Mailbox(models.Model):
    class Mode(models.TextChoices):
        IMPORT = "import", "Import only"
        LIVE = "live", "Live connection"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="mailboxes")
    email = models.EmailField()
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.IMPORT)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["subject", "email"], name="mailbox_unique_email_per_subject")]

    def __str__(self):
        return self.email


class IdentifyingDetail(models.Model):
    class Kind(models.TextChoices):
        CUSTOMER_NUMBER = "customer_number", "Customer number"
        PREVIOUS_ADDRESS = "previous_address", "Previous address"
        DATE_OF_BIRTH = "date_of_birth", "Date of birth"
        OTHER = "other", "Other"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="details")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    value = models.CharField(max_length=500)
    # A plain label for now; a later ticket links it to the Organization model.
    organization_label = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["kind", "id"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"


class Consent(models.Model):
    class GivenBy(models.TextChoices):
        SUBJECT = "subject", "The Subject"
        PARENT = "parent", "A parent (for a child)"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="consents")
    given_by = models.CharField(max_length=10, choices=GivenBy.choices)
    given_at = models.DateTimeField(default=timezone.now)
    scope = models.TextField(help_text="Version and wording of the scope that was agreed to.")
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-given_at", "-id"]

    def __str__(self):
        return f"Consent of {self.subject} at {self.given_at:%Y-%m-%d}"

    @property
    def is_active(self):
        return self.withdrawn_at is None
