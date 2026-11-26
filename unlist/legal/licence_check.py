# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Release check: every runtime package has an allowed licence and a section in THIRD-PARTY-NOTICES.

"Runtime package" has one definition: a distribution that `requirements.txt` names, or that
one of those requires (recursively), ignoring optional extras and any requirement that is not
installed (for example `tzdata`, which only Windows needs). Development tools such as ruff,
pip and setuptools are never reachable that way, so they are ignored without a list.
"""

import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from unlist.paths import BASE_DIR

ALLOW_LIST = Path(__file__).with_name("licences.json")
NOTICES = BASE_DIR / "THIRD-PARTY-NOTICES"
REQUIREMENTS = BASE_DIR / "requirements.txt"

# Licences (SPDX identifiers) that may be combined with the AGPL-3.0-or-later.
AGPL_COMPATIBLE = {
    "0BSD",
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "ISC",
    "LGPL-3.0-or-later",
    "MIT",
    "MIT-0",
    "MPL-2.0",
    "PSF-2.0",
    "Python-2.0",
    "Unlicense",
}

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_HEADER = re.compile(r"^=== (.+?) \(.*\) ===$", re.MULTILINE)


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_requirements(path: Path = REQUIREMENTS) -> list[str]:
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        match = _NAME.match(line)
        if match:
            names.append(match.group(0))
    return names


def runtime_distributions(roots: list[str]) -> tuple[dict, list[str]]:
    """Return ({canonical name: distribution}, problems) for the roots and everything they require."""
    found, problems, queue = {}, [], list(roots)
    root_names = {canonical(r) for r in roots}
    while queue:
        name = queue.pop()
        key = canonical(name)
        if key in found:
            continue
        try:
            dist = distribution(name)
        except PackageNotFoundError:
            if key in root_names:
                problems.append(f"{name} is in requirements.txt but not installed")
            continue
        found[key] = dist
        for requirement in dist.requires or []:
            spec, _, marker = requirement.partition(";")
            if "extra" in marker:
                continue
            match = _NAME.match(spec.strip())
            if match:
                queue.append(match.group(0))
    return found, problems


def declared_licence(dist) -> str | None:
    meta = dist.metadata
    value = meta.get("License-Expression") or meta.get("License")
    if value and len(value) <= 100 and "\n" not in value:
        return value.strip()
    return None


def _normal(expression: str) -> str:
    return re.sub(r"\s+", " ", expression).strip().lower()


def notice_names(text: str) -> set[str]:
    return {canonical(name) for name in _HEADER.findall(text)}


def check(allow_list: dict[str, str], notices_text: str, requirements: list[str]) -> tuple[list[str], list[str]]:
    """Return (problems, lines describing what was checked)."""
    found, problems = runtime_distributions(requirements)
    allowed = {canonical(name): licence for name, licence in allow_list.items()}
    in_notices = notice_names(notices_text)
    report = []
    for key in sorted(found):
        dist = found[key]
        name = dist.metadata["Name"]
        if key not in allowed:
            problems.append(f"{name}: not in unlist/legal/licences.json")
        else:
            expression = allowed[key]
            tokens = {t for t in re.split(r"\s+(?:AND|OR|WITH)\s+|[()]", expression) if t.strip()}
            for token in tokens:
                if token.strip() not in AGPL_COMPATIBLE:
                    problems.append(f"{name}: {token.strip()} is not on the AGPL-compatible list")
            declared = declared_licence(dist)
            if declared is not None and _normal(declared) != _normal(expression):
                problems.append(f"{name}: installed metadata says {declared!r}, licences.json says {expression!r}")
        if key not in in_notices:
            problems.append(f"{name}: no section in THIRD-PARTY-NOTICES")
        report.append(f"{name} {dist.version}: {allowed.get(key, '?')}")
    return problems, report


def run() -> tuple[list[str], list[str]]:
    allow_list = json.loads(ALLOW_LIST.read_text(encoding="utf-8"))
    return check(allow_list, NOTICES.read_text(encoding="utf-8"), read_requirements())
