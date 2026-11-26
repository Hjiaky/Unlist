# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Tests for tools/organization-list/build.py on a tiny datenanfragen-shaped tree."""

import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TOOLS = Path(settings.BASE_DIR) / "tools" / "organization-list"
APP = Path(__file__).resolve().parent.parent


def load_build():
    spec = importlib.util.spec_from_file_location("organization_list_build", TOOLS / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_build()


def company(slug, **fields):
    record = {
        "slug": slug,
        "relevant-countries": ["de"],
        "name": f"{slug.title()} GmbH",
        "address": "Straße 1\n10115 Berlin\nDeutschland",
        "sources": [f"https://{slug}.example/datenschutz"],
        "quality": "verified",
    }
    record.update(fields)
    return record


class BuildTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.upstream = self.tmp / "data"
        self.overlay = self.tmp / "overlay"
        for directory in ["companies", "obsolete-records", "supervisory-authorities"]:
            (self.upstream / directory).mkdir(parents=True)
        for directory in ["organizations", "brokers"]:
            (self.overlay / directory).mkdir(parents=True)
        shutil.copy(TOOLS / "schema.json", self.overlay / "schema.json")
        self.write(self.overlay / "ambiguous-domains.json", {"domains": ["gmail.com"]})
        self.write_company(company("alpha", email="datenschutz@alpha.example", web="https://www.alpha.example/"))
        self.write_company(company("beta", email="max.mustermann@beta.example", web="https://beta.example"))
        self.write_company(company("gamma", web="https://shared.example", **{"suggested-transport-medium": "fax"}))
        self.write_company(company("delta", web="https://shared.example/de"))
        self.write(
            self.upstream / "obsolete-records" / "oldco.json",
            {
                "slug": "oldco",
                "name": "OldCo",
                "reason": "company-merged",
                "redirect-to": "alpha",
                "quality": "obsolete",
            },
        )
        self.write(
            self.upstream / "supervisory-authorities" / "xxdpa.json",
            {"slug": "xxdpa", "relevant-countries": ["de"], "name": "DPA", "address": "A\nB", "sources": []},
        )

    def write(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def write_company(self, record):
        self.write(self.upstream / "companies" / f"{record['slug']}.json", record)

    def run_build(self, **kwargs):
        return build.build(
            self.upstream, overlay_dir=self.overlay, date="2026-11-26", upstream_commit="a" * 40, **kwargs
        )

    def records(self, outputs):
        return {r["slug"]: r for r in outputs["organizations.json"]["records"]}

    def test_build_writes_a_valid_list(self):
        outputs, report = self.run_build()
        header = outputs["organizations.json"]["header"]
        self.assertEqual(header["licence"], "CC0-1.0")
        self.assertEqual(header["schema_version"], 1)
        self.assertEqual(header["sources"][0]["commit"], "a" * 40)
        records = self.records(outputs)
        self.assertEqual(records["alpha"]["domains"], ["alpha.example"])
        self.assertEqual(records["gamma"]["suggested-transport-medium"], "letter")
        self.assertEqual(outputs["organizations.json"]["obsolete"][0]["redirect-to"], "alpha")
        self.assertEqual(len(outputs["supervisory-authorities.json"]["records"]), 1)
        text = build.serialize(outputs["organizations.json"])
        self.assertEqual(json.loads(text), outputs["organizations.json"])
        self.assertEqual(report["counts"]["organizations"], 4)

    def test_named_person_address_is_flagged_and_withheld(self):
        outputs, report = self.run_build()
        beta = self.records(outputs)["beta"]
        self.assertNotIn("email", beta)
        self.assertIn("named person", beta["notes"][0])
        self.assertEqual(report["named_person_emails"], ["beta"])
        self.assertEqual(self.records(outputs)["alpha"]["email"], "datenschutz@alpha.example")

    def test_duplicate_domain_fails_the_build(self):
        self.write(self.overlay / "organizations" / "alpha.json", {"domains": ["dup.example"]})
        self.write(self.overlay / "organizations" / "beta.json", {"domains": ["dup.example"]})
        with self.assertRaises(build.BuildError) as raised:
            self.run_build()
        self.assertIn("dup.example is claimed by more than one record", raised.exception.errors[0])

    def test_shared_web_host_is_left_unassigned(self):
        outputs, report = self.run_build()
        records = self.records(outputs)
        self.assertNotIn("domains", records["gamma"])
        self.assertNotIn("domains", records["delta"])
        self.assertEqual(report["shared_web_domains_dropped"], {"shared.example": ["delta", "gamma"]})

    def test_overlay_and_broker_records(self):
        self.write(self.overlay / "organizations" / "alpha.json", {"broker": True, "last-checked": "2026-11-26"})
        broker = {"slug": "newbroker", "name": "New Broker Ltd", "domains": ["newbroker.example"], "broker": True}
        self.write(self.overlay / "brokers" / "newbroker.json", broker)
        outputs, report = self.run_build()
        records = self.records(outputs)
        self.assertTrue(records["alpha"]["broker"])
        self.assertEqual(records["newbroker"]["domains"], ["newbroker.example"])
        self.assertEqual(report["counts"]["brokers_flagged_upstream"], 1)
        self.assertEqual(report["counts"]["broker_records_added"], 1)

    def test_invalid_record_and_unknown_overlay_fail_the_build(self):
        self.write(self.overlay / "organizations" / "nobody.json", {"broker": True})
        self.write_company(company("broken", web="htps//nope"))
        with self.assertRaises(build.BuildError) as raised:
            self.run_build()
        text = "\n".join(raised.exception.errors)
        self.assertIn("nobody.json: no upstream record", text)
        self.assertIn("record broken.web", text)

    def test_ambiguous_domain_cannot_be_claimed(self):
        self.write(self.overlay / "organizations" / "alpha.json", {"domains": ["gmail.com"]})
        with self.assertRaises(build.BuildError):
            self.run_build()

    def test_jdm_domains_map_onto_official_slugs(self):
        jdm = self.tmp / "jdm"
        (jdm / "_data").mkdir(parents=True)
        (jdm / "LICENSE").write_text("The MIT License (MIT)\n\nCopyright (c) test\n")
        sites = [
            {
                "name": "Alpha",
                "url": "https://alpha.example/delete",
                "domains": ["alpha.example", "alpha.de", "other.example"],
            },
            {"name": "Unknown", "url": "https://unknown.example", "domains": ["unknown.example"]},
        ]
        self.write(jdm / "_data" / "sites.json", sites)
        outputs, report = self.run_build(jdm=jdm)
        jdm_list = outputs["jdm-domains.json"]
        self.assertEqual(jdm_list["header"]["licence"], "MIT")
        self.assertIn("Copyright (c) test", jdm_list["header"]["notice"])
        self.assertEqual(jdm_list["records"], [{"slug": "alpha", "name": "Alpha", "domains": ["alpha.de"]}])
        self.assertEqual(report["jdm"]["sites_unmatched"], 1)

    def test_looks_like_person(self):
        self.assertTrue(build.looks_like_person("Klaus.Molitoris@stmwk.example"))
        self.assertTrue(build.looks_like_person("anna-lena_schmidt@x.example"))
        for role in [
            "datenschutz.de@crif.example",
            "privacy@x.example",
            "data.protection@x.example",
            "koenigslutter.pfa@x",
        ]:
            self.assertFalse(build.looks_like_person(role), role)


class ValidatorCopyTests(SimpleTestCase):
    def test_the_app_and_the_build_share_one_validator(self):
        def block(path):
            text = path.read_text(encoding="utf-8")
            return text[text.index("# --- validator begin ---") : text.index("# --- validator end ---")]

        self.assertEqual(block(TOOLS / "build.py"), block(APP / "validation.py"))

    def test_bundled_schema_matches_the_tooling(self):
        self.assertEqual(
            json.loads((TOOLS / "schema.json").read_text()), json.loads((APP / "data" / "schema.json").read_text())
        )
