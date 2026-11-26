# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.test import SimpleTestCase

from unlist.mail import psl
from unlist.organizations import domains

# The Public Suffix List project's standard test cases (tests/test_psl.txt), plus a few for
# the PRIVATE section. Expected results are in their ASCII (Punycode) form.
CASES = [
    # null input and mixed case
    (None, None),
    ("", None),
    ("COM", None),
    ("example.COM", "example.com"),
    ("WwW.example.COM", "example.com"),
    # leading dot
    (".com", None),
    (".example", None),
    (".example.com", None),
    (".example.example", None),
    # unlisted TLD: the implicit "*" rule
    ("example", None),
    ("example.example", "example.example"),
    ("b.example.example", "example.example"),
    ("a.b.example.example", "example.example"),
    # listed, but non-Internet, TLD and TLDs with one rule
    ("biz", None),
    ("domain.biz", "domain.biz"),
    ("b.domain.biz", "domain.biz"),
    ("a.b.domain.biz", "domain.biz"),
    ("com", None),
    ("example.com", "example.com"),
    ("b.example.com", "example.com"),
    ("a.b.example.com", "example.com"),
    ("uk.com", None),
    ("example.uk.com", "example.uk.com"),
    ("b.example.uk.com", "example.uk.com"),
    ("a.b.example.uk.com", "example.uk.com"),
    ("test.ac", "test.ac"),
    ("www.example.co.uk", "example.co.uk"),
    # TLD with only one (wildcard) rule
    ("mm", None),
    ("c.mm", None),
    ("b.c.mm", "b.c.mm"),
    ("a.b.c.mm", "b.c.mm"),
    # more complex TLD
    ("jp", None),
    ("test.jp", "test.jp"),
    ("www.test.jp", "test.jp"),
    ("ac.jp", None),
    ("test.ac.jp", "test.ac.jp"),
    ("www.test.ac.jp", "test.ac.jp"),
    ("kyoto.jp", None),
    ("test.kyoto.jp", "test.kyoto.jp"),
    ("ide.kyoto.jp", None),
    ("b.ide.kyoto.jp", "b.ide.kyoto.jp"),
    ("a.b.ide.kyoto.jp", "b.ide.kyoto.jp"),
    ("c.kobe.jp", None),
    ("b.c.kobe.jp", "b.c.kobe.jp"),
    ("a.b.c.kobe.jp", "b.c.kobe.jp"),
    ("city.kobe.jp", "city.kobe.jp"),
    ("www.city.kobe.jp", "city.kobe.jp"),
    # TLD with a wildcard rule and exceptions
    ("ck", None),
    ("test.ck", None),
    ("b.test.ck", "b.test.ck"),
    ("a.b.test.ck", "b.test.ck"),
    ("www.ck", "www.ck"),
    ("www.www.ck", "www.ck"),
    # US K12
    ("us", None),
    ("test.us", "test.us"),
    ("www.test.us", "test.us"),
    ("ak.us", None),
    ("test.ak.us", "test.ak.us"),
    ("www.test.ak.us", "test.ak.us"),
    ("k12.ak.us", None),
    ("test.k12.ak.us", "test.k12.ak.us"),
    ("www.test.k12.ak.us", "test.k12.ak.us"),
    # IDN labels
    ("食狮.com.cn", "xn--85x722f.com.cn"),
    ("食狮.公司.cn", "xn--85x722f.xn--55qx5d.cn"),
    ("www.食狮.公司.cn", "xn--85x722f.xn--55qx5d.cn"),
    ("shishi.公司.cn", "shishi.xn--55qx5d.cn"),
    ("公司.cn", None),
    ("食狮.中国", "xn--85x722f.xn--fiqs8s"),
    ("www.食狮.中国", "xn--85x722f.xn--fiqs8s"),
    ("shishi.中国", "shishi.xn--fiqs8s"),
    ("中国", None),
    # the same, already in Punycode
    ("xn--85x722f.com.cn", "xn--85x722f.com.cn"),
    ("xn--85x722f.xn--55qx5d.cn", "xn--85x722f.xn--55qx5d.cn"),
    ("www.xn--85x722f.xn--55qx5d.cn", "xn--85x722f.xn--55qx5d.cn"),
    ("shishi.xn--55qx5d.cn", "shishi.xn--55qx5d.cn"),
    ("xn--55qx5d.cn", None),
    ("xn--85x722f.xn--fiqs8s", "xn--85x722f.xn--fiqs8s"),
    ("www.xn--85x722f.xn--fiqs8s", "xn--85x722f.xn--fiqs8s"),
    ("shishi.xn--fiqs8s", "shishi.xn--fiqs8s"),
    ("xn--fiqs8s", None),
    # the PRIVATE section is used
    ("myshopify.com", None),
    ("shop-a.myshopify.com", "shop-a.myshopify.com"),
    ("www.shop-a.myshopify.com", "shop-a.myshopify.com"),
    ("someone.github.io", "someone.github.io"),
    # a trailing dot is ignored; empty labels are not a host
    ("example.com.", "example.com"),
    ("a..example.com", None),
]


class PublicSuffixListTests(SimpleTestCase):
    def test_standard_cases(self):
        for host, expected in CASES:
            with self.subTest(host=host):
                self.assertEqual(psl.registrable_domain(host), expected)

    def test_public_suffix(self):
        self.assertEqual(psl.public_suffix("www.example.co.uk"), "co.uk")
        self.assertEqual(psl.public_suffix("b.test.ck"), "test.ck")
        self.assertEqual(psl.public_suffix("www.ck"), "ck")

    def test_the_list_is_parsed_once(self):
        self.assertIs(psl.rules(), psl.rules())
        normal, wildcard, exception = psl.rules()
        self.assertIn("co.uk", normal)
        self.assertIn("ck", wildcard)
        self.assertIn("www.ck", exception)
        self.assertGreater(len(normal), 5000)


class OrganizationDomainTests(SimpleTestCase):
    """`unlist.organizations.domains` uses the Public Suffix List for registrable domains."""

    def test_registrable_domain(self):
        self.assertEqual(domains.registrable_domain("https://news.shop.co.uk/a"), "shop.co.uk")
        self.assertEqual(domains.registrable_domain("Orders@Mail.Example.COM"), "example.com")
        self.assertIsNone(domains.registrable_domain("not a domain"))

    def test_candidates_stop_at_the_registrable_domain(self):
        self.assertEqual(
            domains.candidates("a.b.example.co.uk"), ["a.b.example.co.uk", "b.example.co.uk", "example.co.uk"]
        )
        self.assertEqual(domains.candidates("example.com"), ["example.com"])
        self.assertEqual(domains.candidates("shop-a.myshopify.com"), ["shop-a.myshopify.com"])
        self.assertEqual(domains.candidates("co.uk"), ["co.uk"])

    def test_shared_platform_subdomains_stay_ambiguous(self):
        self.assertTrue(domains.is_ambiguous("someone.github.io"))
        self.assertTrue(domains.is_ambiguous("bounces.sendgrid.net"))
        self.assertFalse(domains.is_ambiguous("shop.co.uk"))
