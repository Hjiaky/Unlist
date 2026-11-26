# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Replace a Subject's identifying data with placeholders before text goes to the LLM, and back.

What counts: the Subject's name (whole, then each part of three letters or more), their email
addresses (every Mailbox, plus any extra address given, such as a draft's sender), the values
of their identifying details, and a Case reference code. Each becomes ``{{NAME}}``,
``{{NAME_2}}``, ``{{EMAIL}}``, ``{{DETAIL}}``, ``{{REFERENCE}}`` and so on. Matching ignores
case and only takes whole words, longest value first.

Decided by agent (ticket #56): detail values shorter than three characters are left alone (they
identify nobody and would make the text unreadable); name parts count, so "Dear Ms Example"
does not leak the surname.
"""

import re
from dataclasses import dataclass, field

MIN_LENGTH = 3
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z]+(?:_\d+)?\}\}")


def _normalise(value: str) -> str:
    return (value or "").replace("\r\n", "\n").strip()


@dataclass
class Redactor:
    """Placeholders for one Subject's values. ``redact`` and ``restore`` are inverses."""

    values: dict[str, str] = field(default_factory=dict)  # placeholder -> real value

    @classmethod
    def build(cls, *, name="", emails=(), details=(), reference="") -> "Redactor":
        redactor = cls()
        name = " ".join((name or "").split())
        redactor._add("NAME", name)
        for part in re.split(r"[\s\-]+", name):
            if len(part) >= MIN_LENGTH and part.lower() != name.lower():
                redactor._add("NAME", part)
        for address in emails:
            redactor._add("EMAIL", address)
        for value in details:
            redactor._add("DETAIL", value)
        redactor._add("REFERENCE", reference)
        return redactor

    @classmethod
    def for_subject(cls, subject, *, emails=(), reference="") -> "Redactor":
        """Everything Unlist holds that identifies ``subject``, plus ``emails`` and ``reference``."""
        addresses = [*subject.mailboxes.values_list("email", flat=True), *emails]
        details = list(subject.details.values_list("value", flat=True))
        return cls.build(name=subject.name, emails=addresses, details=details, reference=reference)

    def _add(self, kind: str, value: str) -> None:
        value = _normalise(value)
        if len(value) < MIN_LENGTH or any(value.lower() == known.lower() for known in self.values.values()):
            return
        count = sum(1 for placeholder in self.values if placeholder.startswith("{{" + kind))
        placeholder = "{{" + kind + (f"_{count + 1}" if count else "") + "}}"
        self.values[placeholder] = value

    def _pattern(self) -> re.Pattern | None:
        if not self.values:
            return None
        ordered = sorted(self.values.values(), key=len, reverse=True)
        return re.compile(
            "|".join(rf"(?<!\w){re.escape(value)}(?!\w)" for value in ordered), re.IGNORECASE | re.MULTILINE
        )

    def redact(self, text: str) -> str:
        text = (text or "").replace("\r\n", "\n")
        pattern = self._pattern()
        if pattern is None:
            return text
        lookup = {value.lower(): placeholder for placeholder, value in self.values.items()}
        return pattern.sub(lambda match: lookup[match.group(0).lower()], text)

    def restore(self, text: str) -> str:
        return PLACEHOLDER_RE.sub(lambda match: self.values.get(match.group(0), match.group(0)), text or "")

    @staticmethod
    def placeholders_in(text: str) -> set[str]:
        return set(PLACEHOLDER_RE.findall(text or ""))

    def missing_in(self, sent: str, answer: str) -> set[str]:
        """Placeholders the sent text had that the answer lost (a translation must keep all of them)."""
        return {placeholder for placeholder in self.placeholders_in(sent) if placeholder in self.values} - (
            self.placeholders_in(answer)
        )
