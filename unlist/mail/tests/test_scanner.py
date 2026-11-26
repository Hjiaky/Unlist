# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import dataclasses
import email
from email.message import EmailMessage

from django.test import SimpleTestCase

from unlist.mail import scanner

AUTH_OK = "mx.example.net; dmarc=pass header.from={domain}"


def message(sender="Shop <hello@shop.example>", subject="Hello", auth=AUTH_OK, headers=(), html=None, text="Hi"):
    msg = EmailMessage()
    if auth is not None:
        domain = sender.rsplit("@", 1)[-1].strip(">")
        msg["Authentication-Results"] = auth.format(domain=domain)
    msg["From"] = sender
    msg["To"] = "alex@example.org"
    msg["Subject"] = subject
    msg["Date"] = "Mon, 03 Mar 2025 10:15:00 +0100"
    msg["Message-ID"] = "<m1@shop.example>"
    for name, value in headers:
        msg[name] = value
    msg.set_content(text)
    if html is not None:
        msg.add_alternative(html, subtype="html")
    return email.message_from_bytes(msg.as_bytes())  # as an mbox read would give it (compat32)


class AuthenticationResultsTests(SimpleTestCase):
    def test_parse_standard_header(self):
        authserv, results = scanner.parse_authentication_results(
            "mx.google.com;\r\n dkim=pass header.i=@brand.example header.s=s1 header.b=Ab+c;"
            " spf=pass (google.com: domain of x@esp.example designates 192.0.2.1 as permitted sender)"
            " smtp.mailfrom=x@esp.example; dmarc=pass (p=NONE sp=NONE dis=NONE) header.from=brand.example"
        )
        self.assertEqual(authserv, "mx.google.com")
        self.assertEqual([(m, r) for m, r, _ in results], [("dkim", "pass"), ("spf", "pass"), ("dmarc", "pass")])
        self.assertEqual(results[0][2]["header.i"], "@brand.example")
        self.assertEqual(results[2][2]["header.from"], "brand.example")

    def test_parse_microsoft_style_without_authserv_id(self):
        authserv, results = scanner.parse_authentication_results(
            "spf=pass (sender IP is 192.0.2.1) smtp.mailfrom=brand.example; dkim=pass (signature was verified)"
            " header.d=brand.example;dmarc=pass action=none header.from=brand.example;compauth=pass reason=100"
        )
        self.assertEqual(authserv, "")
        self.assertEqual([m for m, _, _ in results], ["spf", "dkim", "dmarc", "compauth"])
        self.assertEqual(results[2][2], {"action": "none", "header.from": "brand.example"})

    def test_parse_tolerates_spaces_quotes_and_missing_semicolons(self):
        _, results = scanner.parse_authentication_results(
            'example.net 1; dkim = pass header.d = "brand.example" dmarc=PASS header.from=brand.example'
        )
        self.assertEqual([(m, r) for m, r, _ in results], [("dkim", "pass"), ("dmarc", "pass")])
        self.assertEqual(results[0][2]["header.d"], "brand.example")
        self.assertEqual(scanner.parse_authentication_results("example.net; none"), ("example.net", []))

    def test_dmarc_pass_authenticates(self):
        self.assertTrue(scanner.scan(message()).authenticated)

    def test_dmarc_pass_for_another_domain_does_not(self):
        result = scanner.scan(message(auth="mx.example.net; dmarc=pass header.from=other.example"))
        self.assertEqual(result.skip, scanner.SKIP_UNAUTHENTICATED)

    def test_aligned_dkim_authenticates(self):
        for auth in [
            "mx.example.net; dkim=pass header.d=shop.example",
            "mx.example.net; dkim=pass header.d=mail.shop.example",
            "mx.example.net; dkim=pass header.i=@news.shop.example",
            "mx.example.net; dkim=pass header.i=orders@shop.example",
        ]:
            with self.subTest(auth=auth):
                self.assertTrue(scanner.scan(message(auth=auth)).authenticated)

    def test_unaligned_dkim_spf_and_failures_do_not(self):
        for auth in [
            "mx.example.net; dkim=pass header.d=esp.example; spf=pass smtp.mailfrom=bounce@esp.example",
            "mx.example.net; spf=pass smtp.mailfrom=orders@shop.example",
            "mx.example.net; dkim=fail header.d=shop.example; dmarc=fail header.from=shop.example",
            "mx.example.net; dmarc=bestguesspass header.from=shop.example",
            "mx.example.net; dkim=pass header.d=example",  # a public suffix, not shop.example
        ]:
            with self.subTest(auth=auth):
                self.assertEqual(scanner.scan(message(auth=auth)).skip, scanner.SKIP_UNAUTHENTICATED)
        self.assertEqual(scanner.scan(message(auth=None)).skip, scanner.SKIP_UNAUTHENTICATED)

    def test_only_the_topmost_header_is_trusted(self):
        msg = message(auth="mx.example.net; dmarc=fail header.from=shop.example")
        msg["Authentication-Results"] = "mx.example.net; dmarc=pass header.from=shop.example"  # added below
        self.assertEqual(scanner.scan(msg).skip, scanner.SKIP_UNAUTHENTICATED)


class BulkTests(SimpleTestCase):
    def test_bulk_markers(self):
        for headers in [
            [("List-Unsubscribe", "<https://shop.example/u>")],
            [("List-Id", "News <news.shop.example>")],
            [("Precedence", "bulk")],
            [("Precedence", "List")],
            [("Precedence", "junk")],
            [("Auto-Submitted", "auto-generated")],
            [("Auto-Submitted", "auto-replied; owner-email=x@shop.example")],
        ]:
            with self.subTest(headers=headers):
                self.assertTrue(scanner.scan(message(headers=headers)).is_bulk)

    def test_not_bulk(self):
        for headers in [[], [("Auto-Submitted", "no")], [("Precedence", "first-class")]]:
            with self.subTest(headers=headers):
                self.assertFalse(scanner.scan(message(headers=headers)).is_bulk)


class EvidenceTests(SimpleTestCase):
    def evidence(self, **kwargs):
        return scanner.scan(message(**kwargs)).evidence

    def test_json_ld_order_markup(self):
        html = (
            '<html><body><script type="application/ld+json">{"@context": "http://schema.org", "@type": "Order",'
            ' "orderNumber": "1"}</script><p>Thanks</p></body></html>'
        )
        self.assertEqual(self.evidence(html=html, subject="Thanks!"), scanner.ORDER_MARKUP)

    def test_json_ld_in_a_graph_or_list_and_reservations(self):
        for block in [
            '{"@graph": [{"@type": "WebPage"}, {"@type": "ParcelDelivery"}]}',
            '[{"@type": "FlightReservation", "reservationNumber": "X"}]',
            '{"@type": ["Thing", "http://schema.org/Invoice"]}',
            '{"@type": "LodgingReservation", broken json',
        ]:
            with self.subTest(block=block):
                html = f'<script type="application/ld+json">{block}</script>'
                self.assertEqual(self.evidence(html=html), scanner.ORDER_MARKUP)

    def test_microdata_markup(self):
        html = '<div itemscope itemtype="http://schema.org/Order"><span itemprop="orderNumber">1</span></div>'
        self.assertEqual(self.evidence(html=html), scanner.ORDER_MARKUP)

    def test_other_markup_is_not_order_evidence(self):
        html = '<script type="application/ld+json">{"@type": "EmailMessage", "potentialAction": {}}</script>'
        self.assertEqual(self.evidence(html=html, subject="Hello"), scanner.NONE)

    def test_markup_in_an_attached_message_is_ignored(self):
        inner = EmailMessage()
        inner["From"] = "Other <orders@other.example>"
        inner.set_content('<div itemscope itemtype="https://schema.org/Order"></div>', subtype="html")
        outer = EmailMessage()
        outer["Authentication-Results"] = AUTH_OK.format(domain="shop.example")
        outer["From"] = "Shop <hello@shop.example>"
        outer["Subject"] = "Fwd: something"
        outer.set_content("See attached.")
        outer.add_attachment(inner)  # message/rfc822
        parsed = email.message_from_bytes(outer.as_bytes())
        self.assertIn("message/rfc822", [part.get_content_type() for part in parsed.walk()])
        self.assertEqual(scanner.scan(parsed).evidence, scanner.NONE)

    def test_transaction_keywords(self):
        for subject, sender in [
            ("Your order #123 has shipped", "Shop <noreply@shop.example>"),
            ("Ihre Bestellung bei Shop", "Shop <noreply@shop.example>"),
            ("Ihre Rechnung für März", "Shop <noreply@shop.example>"),
            ("Versandbestätigung", "Shop <noreply@shop.example>"),
            ("Hello", "Shop <orders@shop.example>"),
            ("Hello", "Shop <billing-noreply@shop.example>"),
        ]:
            with self.subTest(subject=subject, sender=sender):
                self.assertEqual(self.evidence(subject=subject, sender=sender), scanner.TRANSACTION)

    def test_account_keywords(self):
        for subject, sender in [
            ("Welcome to Shop", "Shop <hello@shop.example>"),
            ("Please verify your email address", "Shop <hello@shop.example>"),
            ("Passwort zurücksetzen", "Shop <hello@shop.example>"),
            ("Neue Anmeldung bei Ihrem Konto", "Shop <hello@shop.example>"),
            ("We're updating our Privacy Policy", "Shop <hello@shop.example>"),
            ("Änderungen unserer AGB", "Shop <hello@shop.example>"),
            ("Hello", "Shop <security@shop.example>"),
        ]:
            with self.subTest(subject=subject, sender=sender):
                self.assertEqual(self.evidence(subject=subject, sender=sender), scanner.ACCOUNT)

    def test_keywords_start_words(self):
        self.assertEqual(self.evidence(subject="Monatsabrechnung", sender="S <hello@shop.example>"), scanner.NONE)
        self.assertEqual(self.evidence(subject="Reorder today", sender="S <hello@shop.example>"), scanner.NONE)

    def test_bulk_without_keywords(self):
        self.assertEqual(
            self.evidence(subject="Autumn sale", headers=[("List-Unsubscribe", "<https://x/u>")]), scanner.BULK
        )

    def test_keywords_beat_bulk(self):  # policy notices are usually bulk-sent
        headers = [("List-Unsubscribe", "<https://x/u>")]
        self.assertEqual(self.evidence(subject="Updates to our terms of service", headers=headers), scanner.ACCOUNT)

    def test_order_of_strength(self):
        self.assertEqual(scanner.stronger(scanner.BULK, scanner.ACCOUNT), scanner.ACCOUNT)
        self.assertEqual(scanner.stronger(scanner.ORDER_MARKUP, scanner.TRANSACTION), scanner.ORDER_MARKUP)
        self.assertEqual(scanner.stronger(scanner.NONE, scanner.BULK), scanner.BULK)


class SkipTests(SimpleTestCase):
    def test_personal_mail_is_skipped(self):
        for sender in [
            "Mary <mary@gmail.com>",
            "Mary <mary@googlemail.com>",
            "Mary <mary@hotmail.co.uk>",
            "Mary <mary@yahoo.de>",
            "Mary <mary@gmx.net>",
            "Mary <mary@web.de>",
            "Mary <mary@posteo.de>",
            "Mary <mary@proton.me>",
        ]:
            with self.subTest(sender=sender):
                result = scanner.scan(message(sender=sender, subject="Your order"))
                self.assertEqual(result.skip, scanner.SKIP_PERSONAL)
                self.assertEqual(result.subject, "")  # personal subject lines never leave the scanner

    def test_bulk_mail_from_a_personal_provider_is_not_personal(self):
        result = scanner.scan(message(sender="Club <club@gmail.com>", headers=[("List-Id", "<club.example>")]))
        self.assertIsNone(result.skip)

    def test_the_subjects_own_address_is_personal(self):
        result = scanner.scan(message(sender="Alex <alex@own.example>"), own_addresses={"alex@own.example"})
        self.assertEqual(result.skip, scanner.SKIP_PERSONAL)

    def test_takeout_spam_and_trash_are_skipped(self):
        for labels in ["Spam", "Trash", "Inbox,Spam", "Opened,Trash,Category Promotions"]:
            with self.subTest(labels=labels):
                result = scanner.scan(message(headers=[("X-Gmail-Labels", labels)]))
                self.assertEqual(result.skip, scanner.SKIP_SPAM)
        self.assertIsNone(scanner.scan(message(headers=[("X-Gmail-Labels", "Inbox,Important")])).skip)

    def test_no_sender(self):
        for sender in ["", "undisclosed-recipients:;", "Nobody <nobody>"]:
            with self.subTest(sender=sender):
                self.assertEqual(scanner.scan(message(sender=sender, auth=None)).skip, scanner.SKIP_NO_SENDER)


class ResultTests(SimpleTestCase):
    def test_result_fields(self):
        msg = message(
            sender="=?utf-8?q?M=C3=BCller_Shop?= <Orders@Mail.Shop.co.uk>",
            subject="=?utf-8?q?Ihre_Bestellbest=C3=A4tigung?=",
            auth="mx.example.net; dkim=pass header.d=shop.co.uk",
            text="SECRET BODY TEXT",
        )
        result = scanner.scan(msg)
        self.assertEqual(result.sender_address, "orders@mail.shop.co.uk")
        self.assertEqual(result.sender_host, "mail.shop.co.uk")
        self.assertEqual(result.sender_domain, "shop.co.uk")
        self.assertEqual(result.display_name, "Müller Shop")
        self.assertEqual(result.subject, "Ihre Bestellbestätigung")
        self.assertEqual(result.date.isoformat(), "2025-03-03T10:15:00+01:00")
        self.assertEqual(result.message_id, "<m1@shop.example>")
        self.assertEqual(result.evidence, scanner.TRANSACTION)
        self.assertTrue(result.discoverable)
        for value in dataclasses.asdict(result).values():
            self.assertNotIn("SECRET", str(value))

    def test_headers_only_message(self):
        """An IMAP scan fetches only header fields; the scanner works on those alone."""
        raw = (
            b"Authentication-Results: mx.example.net; dmarc=pass header.from=shop.example\r\n"
            b"From: Shop <noreply@shop.example>\r\nSubject: Welcome to Shop\r\n"
            b"Date: Tue, 01 Apr 2025 12:00:00 +0000\r\n\r\n"
        )
        result = scanner.scan(email.message_from_bytes(raw))
        self.assertEqual((result.sender_domain, result.evidence), ("shop.example", scanner.ACCOUNT))

    def test_bad_date_and_unknown_charset(self):
        raw = (
            b"Authentication-Results: mx.example.net; dmarc=pass header.from=shop.example\r\n"
            b"From: Shop <noreply@shop.example>\r\nSubject: Hi\r\nDate: someday\r\n"
            b"Content-Type: text/html; charset=x-unknown\r\n\r\n<div itemtype='http://schema.org/Order'></div>\r\n"
        )
        result = scanner.scan(email.message_from_bytes(raw))
        self.assertIsNone(result.date)
        self.assertEqual(result.evidence, scanner.ORDER_MARKUP)
