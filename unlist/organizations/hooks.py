# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Hooks other apps register so this app can ask about them without importing them.

`has_case` holds callables `slug -> bool`. The Cases app appends one that says whether a
Case exists for the Organization with that slug. With nothing registered, no Organization
has a Case.
"""

has_case = []


def organization_has_case(slug):
    return any(check(slug) for check in has_case)
