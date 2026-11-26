# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.test import SimpleTestCase

from unlist.organizations.merge import LOCAL, ListInput, domain_owners, merge


def lst(key, records, obsolete=None):
    return ListInput(key=key, name=f"list {key}", records={r["slug"]: r for r in records}, obsolete=obsolete or {})


class MergeOrderTests(SimpleTestCase):
    def test_highest_list_with_a_value_wins_per_field(self):
        high = lst(1, [{"slug": "acme", "name": "ACME Ltd", "email": "privacy@acme.example"}])
        low = lst(2, [{"slug": "acme", "name": "Acme", "email": "old@acme.example", "address": "1 Road\nTown"}])
        org = merge([high, low]).organizations["acme"]
        self.assertEqual(org.values["name"], "ACME Ltd")
        self.assertEqual(org.values["email"], "privacy@acme.example")
        self.assertEqual(org.values["address"], "1 Road\nTown")  # only the lower list has it
        self.assertEqual(org.sources["email"], "list 1")
        self.assertEqual(org.sources["address"], "list 2")

    def test_reordering_the_lists_changes_the_winner(self):
        a = lst(1, [{"slug": "acme", "name": "A"}])
        b = lst(2, [{"slug": "acme", "name": "B"}])
        self.assertEqual(merge([b, a]).organizations["acme"].values["name"], "B")

    def test_local_override_beats_every_list(self):
        high = lst(1, [{"slug": "acme", "name": "ACME", "email": "privacy@acme.example"}])
        result = merge([high], {"acme": {"email": "dpo@acme.example"}})
        org = result.organizations["acme"]
        self.assertEqual(org.values["email"], "dpo@acme.example")
        self.assertEqual(org.sources["email"], LOCAL)

    def test_conflicting_fields_are_recorded(self):
        high = lst(1, [{"slug": "acme", "name": "ACME", "email": "a@acme.example", "phone": "+1 2 3"}])
        low = lst(2, [{"slug": "acme", "name": "ACME", "email": "b@acme.example", "phone": "+1 2 3"}])
        org = merge([high, low]).organizations["acme"]
        self.assertEqual(org.conflicts["email"], [["list 1", "a@acme.example"], ["list 2", "b@acme.example"]])
        self.assertNotIn("phone", org.conflicts)
        self.assertNotIn("name", org.conflicts)

    def test_domains_are_the_union_of_all_lists(self):
        high = lst(1, [{"slug": "acme", "name": "ACME", "domains": ["acme.example"]}])
        low = lst(2, [{"slug": "acme", "name": "ACME", "domains": ["acme.example", "acme-shop.example"]}])
        result = merge([high, low])
        self.assertEqual(result.organizations["acme"].domains, ["acme-shop.example", "acme.example"])
        self.assertEqual(result.owners["acme-shop.example"], "acme")


class MatchingTests(SimpleTestCase):
    def test_records_are_matched_by_slug(self):
        result = merge([lst(1, [{"slug": "acme", "name": "A"}]), lst(2, [{"slug": "acme", "name": "B"}])])
        self.assertEqual(list(result.organizations), ["acme"])

    def test_records_with_different_slugs_are_matched_by_a_shared_domain(self):
        high = lst(1, [{"slug": "acme", "name": "ACME", "domains": ["acme.example"]}])
        low = lst(2, [{"slug": "acme-gmbh", "name": "ACME GmbH", "domains": ["acme.example"], "phone": "+49 30 1"}])
        result = merge([high, low])
        self.assertEqual(list(result.organizations), ["acme"])
        org = result.organizations["acme"]
        self.assertEqual(org.aliases, ["acme-gmbh"])
        self.assertEqual(org.values["phone"], "+49 30 1")
        self.assertEqual(result.owners["acme.example"], "acme")

    def test_an_override_for_an_alias_slug_applies_to_the_merged_organization(self):
        high = lst(1, [{"slug": "acme", "name": "ACME", "domains": ["acme.example"]}])
        low = lst(2, [{"slug": "acme-gmbh", "name": "ACME GmbH", "domains": ["acme.example"]}])
        result = merge([high, low], {"acme-gmbh": {"name": "Acme Mine"}})
        self.assertEqual(result.organizations["acme"].values["name"], "Acme Mine")

    def test_a_domain_claimed_by_two_organizations_matches_neither(self):
        # c shares a domain with both a and b, so it cannot be matched to either.
        high = lst(
            1,
            [
                {"slug": "a", "name": "A", "domains": ["x.example"]},
                {"slug": "b", "name": "B", "domains": ["y.example"]},
            ],
        )
        low = lst(2, [{"slug": "c", "name": "C", "domains": ["x.example", "y.example"]}])
        result = merge([high, low])
        self.assertEqual(set(result.organizations), {"a", "b", "c"})
        self.assertIsNone(result.owners["x.example"])
        self.assertIsNone(result.owners["y.example"])
        self.assertEqual(result.domain_conflicts["x.example"], ["a", "c"])

    def test_a_local_override_of_domains_settles_a_conflict(self):
        high = lst(
            1,
            [
                {"slug": "a", "name": "A", "domains": ["x.example"]},
                {"slug": "b", "name": "B", "domains": ["y.example"]},
            ],
        )
        low = lst(2, [{"slug": "c", "name": "C", "domains": ["x.example", "y.example"]}])
        result = merge([high, low], {"c": {"domains": ["x.example"]}})
        self.assertEqual(result.owners["x.example"], "c")
        self.assertEqual(result.organizations["c"].domains, ["x.example"])
        self.assertEqual(result.owners["y.example"], "b")  # c no longer claims it

    def test_override_for_an_unknown_slug_makes_a_local_stub(self):
        result = merge([], {"local-shop-example": {"name": "Shop", "domains": ["shop.example"]}})
        org = result.organizations["local-shop-example"]
        self.assertTrue(org.local_only)
        self.assertEqual(org.values["quality"], "local")
        self.assertEqual(result.owners["shop.example"], "local-shop-example")


class ObsoleteTests(SimpleTestCase):
    def test_obsolete_redirect_is_followed(self):
        official = lst(
            1,
            [{"slug": "newco", "name": "NewCo", "email": "privacy@newco.example"}],
            obsolete={"oldco": {"name": "OldCo", "redirect-to": "newco"}},
        )
        other = lst(2, [{"slug": "oldco", "name": "OldCo", "domains": ["oldco.example"]}])
        result = merge([official, other])
        self.assertNotIn("oldco", result.organizations)
        self.assertEqual(result.obsolete["oldco"]["redirect_to"], "newco")
        self.assertEqual(result.owners["oldco.example"], "newco")
        self.assertIn("oldco", result.organizations["newco"].aliases)

    def test_redirect_chains_and_cycles(self):
        official = lst(
            1,
            [{"slug": "c", "name": "C"}],
            obsolete={
                "a": {"name": "A", "redirect-to": "b"},
                "b": {"name": "B", "redirect-to": "c"},
                "x": {"name": "X", "redirect-to": "y"},
                "y": {"name": "Y", "redirect-to": "x"},
                "gone": {"name": "Gone"},
            },
        )
        result = merge([official])
        self.assertEqual(result.obsolete["a"]["redirect_to"], "c")
        self.assertIsNone(result.obsolete["x"]["redirect_to"])
        self.assertIsNone(result.obsolete["gone"]["redirect_to"])

    def test_a_higher_list_keeps_a_slug_active(self):
        high = lst(1, [{"slug": "oldco", "name": "OldCo"}])
        low = lst(
            2, [{"slug": "newco", "name": "NewCo"}], obsolete={"oldco": {"name": "OldCo", "redirect-to": "newco"}}
        )
        self.assertIn("oldco", merge([high, low]).organizations)


class DomainOwnerTests(SimpleTestCase):
    def test_owner_rules(self):
        claims = [("one.example", 1, "a"), ("two.example", 1, "a"), ("two.example", 2, "b"), ("two.example", None, "b")]
        self.assertEqual(domain_owners(claims), {"one.example": "a", "two.example": "b"})
        self.assertEqual(domain_owners([("d.example", None, "a"), ("d.example", None, "b")]), {"d.example": None})
