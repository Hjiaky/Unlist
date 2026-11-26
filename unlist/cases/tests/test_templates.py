# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Request templates in English and German (#43)."""

import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from unlist.cases import templating
from unlist.cases.templating import (
    KINDS,
    REQUIRED_VARIABLES,
    TEMPLATE_DIR,
    UK_ONLY_KINDS,
    MissingVariableError,
    render,
    template_language,
)

REFERENCE = "U-7KQ3"

FULL = {
    "jurisdiction": "EU",
    "reference": REFERENCE,
    "subject_name": "Alex Example",
    "subject_email": "alex@example.org",
    "organization_name": "Example Data Ltd",
    "identifying_details": ["Customer number: 12345", "Date of birth: 1 April 1990"],
    "erasure_grounds": ["no_longer_necessary", "consent_withdrawn", "objection", "unlawful"],
    "objection_grounds": "My home address is confidential because of my work.",
    "is_broker": True,
    "original_kind": "access_request",
    "original_date": "2 October 2026",
    "deadline_date": "2 November 2026",
    "original_body": "Dear Sir or Madam, ...",
    "details": ["Customer number: 12345"],
    "offered_details": ["my customer number", "the date of my last order"],
    "refusal_date": "3 November 2026",
    "cited_exception": "retention duties under tax law",
    "operator_name": "Sam Example",
    "letter_date": "26 November 2026",
    "parent_name": "Pat Example",
    "infringement": "The organisation did not answer my access request within one month.",
    "remedy": "Please ask the organisation to answer my request.",
    "supervisory_authority_name": "Example Data Protection Authority",
    "subject_contact_details": ["Postal address: 1 Example Road, Exampletown"],
    "organization_contacts": ["Privacy contact: privacy@example.com"],
    "timeline": ["2 October 2026: access request sent", "16 November 2026: reminder sent"],
    "prior_contact": "Yes, by email: the request and a reminder (attached).",
    "attachments": ["The access request with headers", "The reminder"],
}

# Words and phrases that would make a request read as a threat or a claim for money.
FORBIDDEN = [
    r"compensation",
    r"schadens?ersatz",
    r"entschädigung",
    r"damages",
    r"lawsuit",
    r"\bsue\b",
    r"\bklage",
    r"legal action",
    r"rechtliche schritte",
    r"reserve the right",
    r"behalte ich mir vor",
    r"anwalt",
    r"lawyer",
    r"solicitor",
    r"bußgeld",
    r"\bfines?\b",
    r"threat",
]


def minimal(kind, **extra):
    return {name: FULL[name] for name in REQUIRED_VARIABLES[kind]} | extra


def combinations():
    """Every (kind, lang, jurisdiction) that exists."""
    for kind in KINDS:
        for lang in ("en", "de"):
            for jurisdiction in ("EU", "UK"):
                if kind in UK_ONLY_KINDS and jurisdiction != "UK":
                    continue
                yield kind, lang, jurisdiction


class TemplateTestCase(SimpleTestCase):
    def setUp(self):
        # An empty data directory, so no local override on this machine changes the results.
        self.data_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch("unlist.paths.DATA_DIR", self.data_dir))


class RenderEveryTemplateTests(TemplateTestCase):
    def test_every_template_renders_with_complete_and_with_minimal_data(self):
        for kind, lang, jurisdiction in combinations():
            for context in (FULL, minimal(kind)):
                with self.subTest(kind=kind, lang=lang, jurisdiction=jurisdiction, full=context is FULL):
                    subject, body = render(kind, lang, context | {"jurisdiction": jurisdiction}, strict=True)
                    self.assertNotIn("[[missing", subject + body)
                    self.assertNotIn("{%", body)
                    self.assertNotIn("{{", body)
                    self.assertIn(f"[Ref {REFERENCE}]", subject)
                    self.assertIn(FULL["subject_name"], body)
                    self.assertIn(FULL["subject_email"], body)
                    self.assertNotIn("\n\n\n", body)

    def test_every_kind_exists_in_english_and_german(self):
        for kind in KINDS:
            self.assertTrue((TEMPLATE_DIR / "en" / f"{kind}.txt").is_file(), kind)
            if kind not in UK_ONLY_KINDS:
                self.assertTrue((TEMPLATE_DIR / "de" / f"{kind}.txt").is_file(), kind)

    def test_every_template_file_starts_with_a_subject_line_and_a_blank_line(self):
        for path in sorted(TEMPLATE_DIR.glob("*/*.txt")):
            lines = path.read_text(encoding="utf-8").split("\n")
            self.assertTrue(lines[0].startswith("Subject: "), path)
            self.assertEqual(lines[1], "", path)

    def test_request_templates_state_the_one_month_deadline(self):
        for kind in ("access_request", "removal_request", "details_reply", "id_pushback", "reconsider"):
            for lang, words in (("en", r"one[ -]month"), ("de", r"Monat")):
                with self.subTest(kind=kind, lang=lang):
                    self.assertRegex(render(kind, lang, FULL, strict=True)[1], words)


class JurisdictionTests(TemplateTestCase):
    def test_eu_english_cites_the_gdpr(self):
        subject, body = render("access_request", "en", FULL, strict=True)
        self.assertIn("Article 15 GDPR", subject)
        self.assertNotIn("UK GDPR", body)
        self.assertIn("C-154/21", body)
        self.assertIn("a supervisory authority", body)

    def test_uk_cites_the_uk_gdpr_and_the_dpa_2018(self):
        subject, body = render("access_request", "en", FULL | {"jurisdiction": "UK"}, strict=True)
        self.assertIn("Article 15 UK GDPR", subject)
        self.assertIn("Articles 12(3) and 12A UK GDPR", body)
        self.assertIn("section 164A of the Data Protection Act 2018", body)
        self.assertIn("the Information Commission", body)
        self.assertNotIn("C-154/21", body)

    def test_german_cites_the_dsgvo(self):
        subject, body = render("removal_request", "de", FULL, strict=True)
        self.assertIn("Art. 17 DSGVO", subject)
        for citation in ("Art. 17 Abs. 1 DSGVO", "Art. 21 Abs. 2 DSGVO", "Art. 7 Abs. 3 DSGVO", "Art. 19 DSGVO"):
            self.assertIn(citation, body)

    def test_uk_in_german_falls_back_to_english(self):
        self.assertEqual(template_language("access_request", "de", "UK"), "en")
        subject, body = render("access_request", "de", FULL | {"jurisdiction": "UK"}, strict=True)
        self.assertIn("UK GDPR", subject)
        self.assertIn("Dear Sir or Madam", body)

    def test_complaint_cites_article_77_or_section_165(self):
        self.assertIn("Article 77", render("complaint", "en", FULL, strict=True)[1])
        self.assertIn("Art. 77 DSGVO", render("complaint", "de", FULL, strict=True)[0])
        uk = render("complaint", "en", FULL | {"jurisdiction": "UK"}, strict=True)[1]
        self.assertIn("section 165 of the Data Protection Act 2018", uk)
        self.assertNotIn("Article 77", uk)
        self.assertIn(FULL["supervisory_authority_name"], uk)

    def test_uk_complaint_to_the_organization_exists_only_for_the_uk(self):
        with self.assertRaises(ValueError):
            render("uk_complaint_to_organization", "en", FULL)
        body = render("uk_complaint_to_organization", "en", FULL | {"jurisdiction": "UK"}, strict=True)[1]
        self.assertIn("section 164A", body)
        self.assertIn("30 days", body)

    def test_id_pushback_cites_the_edpb_in_the_eu_and_the_ico_in_the_uk(self):
        for lang, para in (("en", "paragraph 73"), ("de", "Rn. 73")):
            body = render("id_pushback", lang, FULL, strict=True)[1]
            self.assertIn("01/2022", body)
            self.assertIn(para, body)
            self.assertIn("75", body)
        uk = render("id_pushback", "en", FULL | {"jurisdiction": "UK"}, strict=True)[1]
        self.assertIn("Article 12(6) UK GDPR", uk)
        self.assertIn("Only request formal identification documents if necessary", uk)
        self.assertNotIn("01/2022", uk)


class RemovalRequestTests(TemplateTestCase):
    def removal(self, lang, jurisdiction="EU", **context):
        return render("removal_request", lang, minimal("removal_request", jurisdiction=jurisdiction, **context))[1]

    def test_suppression_record_only_for_brokers(self):
        for lang, jurisdiction, phrase in (
            ("en", "EU", "suppression record"),
            ("en", "UK", "suppression record"),
            ("de", "EU", "Sperrvermerk"),
        ):
            with self.subTest(lang=lang, jurisdiction=jurisdiction):
                self.assertIn(phrase, self.removal(lang, jurisdiction, is_broker=True))
                self.assertNotIn(phrase, self.removal(lang, jurisdiction, is_broker=False))
                self.assertNotIn(phrase, self.removal(lang, jurisdiction))

    def test_article_21_1_objection_only_when_grounds_are_given(self):
        grounds = FULL["objection_grounds"]
        for lang, citation, quoted in (
            ("en", "Article 21(1)", f'"{grounds}"'),
            ("de", "Art. 21 Abs. 1", f"„{grounds}“"),
        ):
            with self.subTest(lang=lang):
                with_grounds = self.removal(lang, objection_grounds=grounds)
                self.assertIn(citation, with_grounds)
                self.assertIn(quoted, with_grounds)
                for without in (self.removal(lang), self.removal(lang, objection_grounds="")):
                    self.assertNotIn(citation, without)
                    self.assertNotIn(grounds, without)

    def test_direct_marketing_objection_consent_withdrawal_and_recipients_always_present(self):
        for lang, citations in (
            ("en", ["Article 21(2) GDPR", "Article 7(3) GDPR", "Article 19 GDPR", "close it"]),
            ("de", ["Art. 21 Abs. 2 DSGVO", "Art. 7 Abs. 3 DSGVO", "Art. 19 DSGVO", "Konto"]),
        ):
            body = self.removal(lang)
            for citation in citations:
                self.assertIn(citation, body)

    def test_erasure_grounds_select_the_points_of_article_17_1(self):
        body = self.removal("en", erasure_grounds=["objection"])
        self.assertIn("(point (c))", body)
        for point in ("(a)", "(b)", "(d)"):
            self.assertNotIn(f"(point {point})", body)
        body = self.removal("de", erasure_grounds=["no_longer_necessary", "unlawful"])
        self.assertIn("(lit. a)", body)
        self.assertIn("(lit. d)", body)
        self.assertNotIn("(lit. b)", body)

    def test_strict_rejects_unknown_erasure_grounds(self):
        with self.assertRaises(ValueError):
            render("removal_request", "en", minimal("removal_request", erasure_grounds=["revenge"]), strict=True)


class ContentTests(TemplateTestCase):
    def test_only_the_identifying_details_passed_in(self):
        body = render("access_request", "en", minimal("access_request"))[1]
        self.assertNotIn("Other details", body)
        body = render("access_request", "en", minimal("access_request", identifying_details=["Customer number: 9"]))[1]
        self.assertIn("- Customer number: 9", body)

    def test_details_reply_gives_exactly_the_details_listed(self):
        body = render("details_reply", "en", FULL, strict=True)[1]
        self.assertEqual(re.findall(r"^- .*$", body, re.MULTILINE), ["- Customer number: 12345"])

    def test_reminder_names_the_request_its_date_the_deadline_and_gives_14_days(self):
        subject, body = render("reminder", "en", FULL | {"original_kind": "removal_request"}, strict=True)
        self.assertIn("2 October 2026", subject)
        self.assertIn("request for erasure", body)
        self.assertIn("2 November 2026", body)
        self.assertIn("14 days", body)
        self.assertIn("Tagen", render("reminder", "de", FULL, strict=True)[1])

    def test_authority_letter_is_dated_and_names_subject_operator_and_organization(self):
        for context in (minimal("authority_letter"), FULL):
            body = render("authority_letter", "en", context, strict=True)[1]
            for value in ("26 November 2026", "Alex Example", "Sam Example", "Example Data Ltd", "Signature"):
                self.assertIn(value, body)
        self.assertIn("parental responsibility", render("authority_letter", "en", FULL)[1])

    def test_complaint_lists_timeline_and_attachments(self):
        body = render("complaint", "de", FULL, strict=True)[1]
        for line in FULL["timeline"] + FULL["attachments"]:
            self.assertIn(f"- {line}", body)

    def test_no_threats_or_compensation_demands_anywhere(self):
        texts = {str(path): path.read_text(encoding="utf-8") for path in TEMPLATE_DIR.glob("*/*.txt")}
        for kind, lang, jurisdiction in combinations():
            texts[f"{lang}/{kind}/{jurisdiction}"] = "\n".join(
                render(kind, lang, FULL | {"jurisdiction": jurisdiction})
            )
        for name, text in texts.items():
            for pattern in FORBIDDEN:
                self.assertIsNone(re.search(pattern, text, re.IGNORECASE), f"{pattern!r} in {name}")


class RendererTests(TemplateTestCase):
    def write_override(self, lang, kind, text):
        path = self.data_dir / "mail_templates" / lang / f"{kind}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_missing_variables_are_visible_and_strict_mode_raises(self):
        context = minimal("access_request")
        del context["subject_name"]
        subject, body = render("access_request", "en", context)
        self.assertIn("[[missing: subject_name]]", body)
        self.assertEqual(templating.missing_variables(body), ["subject_name"])
        with self.assertRaises(MissingVariableError):
            render("access_request", "en", context, strict=True)

    def test_local_override_wins(self):
        self.write_override("de", "access_request", "Subject: Eigene Anfrage [Ref {{ reference }}]\n\nHallo {{ x }}\n")
        subject, body = render("access_request", "de", FULL | {"x": "Welt"})
        self.assertEqual(subject, f"Eigene Anfrage [Ref {REFERENCE}]")
        self.assertEqual(body, "Hallo Welt\n")

    def test_english_override_does_not_shadow_the_bundled_german_template(self):
        self.write_override("en", "access_request", "Subject: Mine\n\nMine\n")
        self.assertIn("Auskunft", render("access_request", "de", FULL)[0])
        self.assertEqual(render("access_request", "en", FULL)[0], "Mine")

    def test_override_in_a_new_language_is_used(self):
        self.write_override("fr", "access_request", "Subject: Demande [Ref {{ reference }}]\n\nBonjour\n")
        self.assertEqual(render("access_request", "fr", FULL)[0], f"Demande [Ref {REFERENCE}]")

    def test_languages_without_a_template_fall_back_to_english(self):
        for lang in ("fr", "it", "", "../../etc", "DE-at"):
            with self.subTest(lang=lang):
                expected = "de" if lang == "DE-at" else "en"
                self.assertEqual(template_language("access_request", lang, "EU"), expected)
        self.assertIn("Dear Sir or Madam", render("access_request", "fr", FULL)[1])

    def test_override_without_a_subject_line_is_rejected(self):
        self.write_override("en", "reminder", "Hello\n")
        with self.assertRaises(ValueError):
            render("reminder", "en", FULL)

    def test_subject_is_always_one_line(self):
        subject, _ = render("authority_letter", "en", FULL | {"organization_name": "Evil\r\nBcc: x@example.com"})
        self.assertNotIn("\n", subject)
        self.assertNotIn("\r", subject)

    def test_unknown_kind_and_jurisdiction_are_rejected(self):
        with self.assertRaises(ValueError):
            render("threat_letter", "en", FULL)
        with self.assertRaises(ValueError):
            render("access_request", "en", FULL | {"jurisdiction": "US"})
        with self.assertRaises(ValueError):
            render("access_request", "en", {k: v for k, v in FULL.items() if k != "jurisdiction"})

    def test_readme_documents_every_kind_and_every_variable(self):
        readme = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")
        names = set()
        for path in TEMPLATE_DIR.glob("*/*.txt"):
            source = path.read_text(encoding="utf-8")
            names |= set(re.findall(r"\{\{\s*(\w+)", source))
            names |= set(re.findall(r"\{%\s*(?:if|elif)\s+(?:not\s+)?(\w+)", source))
            names |= set(re.findall(r"\bin\s+(\w+)\s*%\}", source))
            names |= set(re.findall(r"(\w+)\s*==", source))
        names.discard("item")  # loop variable
        for name in sorted(names | set().union(*REQUIRED_VARIABLES.values()) | set(KINDS)):
            self.assertIn(f"`{name}`", readme, name)
