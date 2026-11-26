#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Written for the Unlist project; dedicated to the public domain under CC0 1.0 (see LICENSE).
"""Build Unlist's official Organization List from a datenanfragen/data checkout.

Standard library only. The upstream checkout (and the optional JustDeleteMe checkout) are
read as untrusted data: JSON files are parsed, nothing in them is executed, and the git
commit is read from the files under .git rather than by running git.

    python3 -I build.py /path/to/datenanfragen-data --jdm /path/to/jdm --out ./dist

Writes organizations.json (CC0), jdm-domains.json (MIT, only with --jdm),
supervisory-authorities.json (CC0), ambiguous-domains.json and schema.json to --out.
Exits with status 1 and a list of errors when the result is not publishable.
"""

import argparse
import datetime
import json
import pathlib
import re
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA_VERSION = 1
LIST_NAME = "Unlist official Organization List"
HOMEPAGE = "https://github.com/hjiaky/unlist-organizations"
CREDIT = (
    "Seeded from the datarequests.org (Datenanfragen.de) company database, https://github.com/datenanfragen/data, "
    "CC0 1.0. Not endorsed by datarequests.org."
)

# Upstream fields carried into the Unlist record, under the same name.
UPSTREAM_FIELDS = (
    "slug",
    "name",
    "runs",
    "relevant-countries",
    "categories",
    "address",
    "phone",
    "email",
    "webform",
    "web",
    "suggested-transport-medium",
    "required-elements",
    "needs-id-document",
    "request-language",
    "comments",
    "sources",
    "quality",
)

# Local-part words that mark a role mailbox rather than a person (substring match, lowercase).
ROLE_WORDS = (
    "datenschutz privac data protect dpo dsb dsgvo gdpr rgpd avg office buero bureau büro info kontakt contact "
    "service kunden customer support help team legal recht compliance auskunft request anfrage mail post secretar "
    "sekretar abwickl admin web shop sales verkauf presse press marketing account billing rechnung beauftragt "
    "officer controller titolare kundenmanagement enquir question konzern gruppe group schul school verwaltung "
    "gemeinde kirche pfarr pfa amt stadt rathaus personal jobs career noreply reply vorstand represent strasse"
).split()
_NAME_PART = r"[^\W\d_]{3,}(?:-[^\W\d_]{2,})?"
_PERSON_LOCAL_RE = re.compile(rf"^({_NAME_PART})[._]({_NAME_PART})$")


class BuildError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


# --- validator begin ---
# A small JSON Schema validator for the subset schema.json uses. Kept identical in
# unlist/organizations/validation.py (a test compares the two blocks).
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _type_ok(value, name):
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def _format_ok(value, fmt):
    if fmt == "date":
        if not _DATE_RE.match(value):
            return False
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if fmt == "uri":
        parts = urllib.parse.urlsplit(value)
        return parts.scheme in ("http", "https") and bool(parts.netloc)
    if fmt == "email":
        return bool(_EMAIL_RE.match(value))
    if fmt == "domain":
        return bool(_DOMAIN_RE.match(value))
    return True


def validate(value, schema, root=None, path="$"):
    """Return a list of error messages; empty when `value` matches `schema`."""
    root = schema if root is None else root
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        return validate(value, node, root, path)
    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_type_ok(value, t) for t in types):
            return [f"{path}: expected {' or '.join(types)}"]
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: too short")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")
        if "format" in schema and not _format_ok(value, schema["format"]):
            errors.append(f"{path}: {value!r} is not a valid {schema['format']}")
    if _type_ok(value, "number") and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value!r} is below {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(item, sort_keys=True) for item in value]
            if len(seen) != len(set(seen)):
                errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(validate(item, schema["items"], root, f"{path}[{index}]"))
    if isinstance(value, dict):
        for key in schema.get("required", ()):
            if key not in value:
                errors.append(f"{path}: missing {key!r}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(validate(item, properties[key], root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field {key!r}")
    return errors


# --- validator end ---


def host_domain(value):
    """The domain of a URL, bare host or email address: lowercase, without a leading "www.".

    An approximation of the registrable domain. The Public Suffix List is not used here, so
    a subdomain such as shop.example.co.uk stays as it is. Returns None for anything that is
    not a plausible domain (IP addresses, empty hosts).
    """
    value = (value or "").strip()
    if "@" in value and "/" not in value:
        host = value.rsplit("@", 1)[1]
    else:
        host = urllib.parse.urlsplit(value if "//" in value else f"//{value}").hostname or ""
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host if _DOMAIN_RE.match(host) else None


def looks_like_person(email):
    """True when the local part reads like firstname.lastname (a named person's mailbox)."""
    local = email.split("@", 1)[0].lower()
    match = _PERSON_LOCAL_RE.match(local)
    if not match:
        return False
    return not any(word in part for part in match.groups() for word in ROLE_WORDS)


def git_commit(checkout):
    """The checked-out commit, read from .git without running git. None if unknown."""
    git = checkout / ".git"
    try:
        if git.is_file():  # a worktree: "gitdir: <path>"
            git = (checkout / git.read_text().split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text().strip()
        commit = head
        if head.startswith("ref: "):
            ref = head[5:]
            ref_file = git / ref
            commit = None
            if ref_file.is_file():
                commit = ref_file.read_text().strip()
            elif (git / "packed-refs").is_file():
                for line in (git / "packed-refs").read_text().splitlines():
                    if line.endswith(" " + ref):
                        commit = line.split()[0]
    except OSError:
        return None
    return commit if commit and re.fullmatch(r"[0-9a-f]{40}", commit) else None


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_dir(directory):
    """{stem: parsed JSON} for every *.json file directly in `directory` (sorted)."""
    if not directory.is_dir():
        return {}
    return {path.stem: read_json(path) for path in sorted(directory.glob("*.json"))}


def convert_upstream(record):
    out = {key: record[key] for key in UPSTREAM_FIELDS if key in record}
    if out.get("suggested-transport-medium") == "fax":  # Unlist sends no fax; a letter goes to the same address
        out["suggested-transport-medium"] = "letter"
    return out


def build(upstream, overlay_dir=HERE, jdm=None, version=None, date=None, upstream_commit=None):
    """Build all output files in memory. Returns (outputs: {filename: object}, report: dict)."""
    errors = []
    report = {
        "named_person_emails": [],
        "shared_web_domains_dropped": {},
        "ambiguous_web_domains_dropped": [],
        "obsolete_redirects_dropped": [],
    }
    date = date or datetime.date.today().isoformat()
    version = version or date.replace("-", ".")
    schema = read_json(overlay_dir / "schema.json")
    ambiguous_file = read_json(overlay_dir / "ambiguous-domains.json")
    ambiguous = set(ambiguous_file["domains"])

    def is_ambiguous(domain):
        return any(domain == a or domain.endswith("." + a) for a in ambiguous)

    # 1. Upstream records, converted.
    records = {}
    for stem, record in read_dir(upstream / "companies").items():
        if not isinstance(record, dict) or record.get("slug") != stem:
            errors.append(f"companies/{stem}.json: slug does not match the file name")
            continue
        records[stem] = convert_upstream(record)
    if not records:
        errors.append(f"{upstream}: no records under companies/")

    # 2. Unlist's per-record overlay.
    explicit_domains = {}  # slug -> domains named in a `domains` field
    for stem, overlay in read_dir(overlay_dir / "organizations").items():
        if stem not in records:
            errors.append(f"organizations/{stem}.json: no upstream record with this slug")
            continue
        if not isinstance(overlay, dict) or overlay.get("slug", stem) != stem:
            errors.append(f"organizations/{stem}.json: must be an object for slug {stem!r}")
            continue
        records[stem].update({k: v for k, v in overlay.items() if k != "slug"})
        if "domains" in overlay:
            explicit_domains[stem] = list(overlay["domains"])

    # 3. Unlist-only records.
    unlist_only = set()
    for stem, record in read_dir(overlay_dir / "brokers").items():
        if not isinstance(record, dict) or record.get("slug") != stem:
            errors.append(f"brokers/{stem}.json: slug does not match the file name")
            continue
        if stem in records:
            errors.append(f"brokers/{stem}.json: slug already used upstream; use organizations/{stem}.json instead")
            continue
        records[stem] = dict(record)
        unlist_only.add(stem)
        explicit_domains[stem] = list(record.get("domains", []))

    # 4. Named-person contact addresses are published without the email until fixed.
    for slug, record in records.items():
        email = record.get("email")
        if email and looks_like_person(email):
            report["named_person_emails"].append(slug)
            del record["email"]
            record.setdefault("notes", []).append(
                "Email withheld: the upstream address looks like a named person's mailbox. "
                "Use the postal address or web form, or confirm a role address, until the record is fixed."
            )
            if record.get("suggested-transport-medium") == "email":
                record["suggested-transport-medium"] = "webform" if record.get("webform") else "letter"

    # 5. Domains. A `domains` field is a claim, and a domain claimed twice fails the build.
    #    A `web` host is used only where no record claims it and no other record has it.
    claims = {}
    for slug, domains in explicit_domains.items():
        for domain in domains:
            if is_ambiguous(domain):
                errors.append(f"{slug}: {domain} is listed in ambiguous-domains.json and cannot be claimed")
            claims.setdefault(domain, []).append(slug)
    for domain, slugs in sorted(claims.items()):
        if len(slugs) > 1:
            errors.append(f"domain {domain} is claimed by more than one record: {', '.join(sorted(slugs))}")
    derived = {}
    for slug, record in records.items():
        if slug in explicit_domains:
            continue
        domain = host_domain(record.get("web", ""))
        if not domain or domain in claims:
            continue
        if is_ambiguous(domain):
            report["ambiguous_web_domains_dropped"].append(slug)
            continue
        derived.setdefault(domain, []).append(slug)
    for slug in records:
        records[slug].pop("domains", None)
    for domain, slugs in claims.items():
        for slug in slugs:
            records[slug].setdefault("domains", []).append(domain)
    for domain, slugs in derived.items():
        if len(slugs) > 1:
            report["shared_web_domains_dropped"][domain] = sorted(slugs)
        else:
            records[slugs[0]].setdefault("domains", []).append(domain)
    for record in records.values():
        if "domains" in record:
            record["domains"] = sorted(set(record["domains"]))

    # 6. Obsolete records and their redirects.
    obsolete = []
    upstream_obsolete = read_dir(upstream / "obsolete-records")
    for stem, record in upstream_obsolete.items():
        if stem in records:
            errors.append(f"obsolete-records/{stem}.json: slug is also an active record")
            continue
        entry = {"slug": stem, "name": record.get("name", stem)}
        if record.get("reason"):
            entry["reason"] = record["reason"]
        target = record.get("redirect-to")
        if target:
            if target in records or target in upstream_obsolete:
                entry["redirect-to"] = target
            else:
                report["obsolete_redirects_dropped"].append(stem)
        obsolete.append(entry)

    # 7. Validate everything that will be published.
    ordered = [records[slug] for slug in sorted(records)]
    for record in ordered:
        for error in validate(record, schema["definitions"]["record"], schema, f"record {record.get('slug')}"):
            errors.append(error)
    for entry in obsolete:
        errors.extend(validate(entry, schema["definitions"]["obsolete"], schema, f"obsolete {entry['slug']}"))

    sources = [
        {
            "name": "datenanfragen/data",
            "url": "https://github.com/datenanfragen/data",
            "licence": "CC0-1.0",
        }
    ]
    commit = upstream_commit or git_commit(upstream)
    if commit:
        sources[0]["commit"] = commit
    header = {
        "name": LIST_NAME,
        "licence": "CC0-1.0",
        "credit": CREDIT,
        "homepage": HOMEPAGE,
        "version": version,
        "date": date,
        "schema_version": SCHEMA_VERSION,
        "sources": sources,
    }
    outputs = {
        "organizations.json": {"header": header, "records": ordered, "obsolete": obsolete},
        "ambiguous-domains.json": ambiguous_file,
        "schema.json": schema,
    }

    # 8. Supervisory Authorities, unchanged apart from a header.
    sa_schema_path = upstream / "schema-supervisory-authorities.json"
    sa_schema = read_json(sa_schema_path) if sa_schema_path.is_file() else {}
    authorities = []
    for stem, record in read_dir(upstream / "supervisory-authorities").items():
        problems = validate(record, sa_schema) if sa_schema else []
        if record.get("slug") != stem:
            problems.append("slug does not match the file name")
        if problems:
            errors.extend(f"supervisory-authorities/{stem}.json: {p}" for p in problems)
            continue
        authorities.append(record)
    outputs["supervisory-authorities.json"] = {
        "header": {**header, "name": "Supervisory Authorities (from datarequests.org)"},
        "records": authorities,
    }

    # 9. JustDeleteMe domains mapped onto official slugs.
    if jdm is not None:
        outputs["jdm-domains.json"] = build_jdm(jdm, ordered, is_ambiguous, date, version, report)

    report["counts"] = {
        "organizations": len(ordered),
        "brokers_flagged_upstream": sum(1 for r in ordered if r.get("broker") and r["slug"] not in unlist_only),
        "broker_records_added": sum(1 for r in ordered if r.get("broker") and r["slug"] in unlist_only),
        "obsolete": len(obsolete),
        "supervisory_authorities": len(authorities),
        "named_person_emails": len(report["named_person_emails"]),
    }
    if errors:
        raise BuildError(errors)
    return outputs, report


def _normalize_name(name):
    return re.sub(r"[\W_]+", "", name.casefold())


_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "or", "ne", "go", "edu"}


def base_label(domain):
    """The brand label of a domain: "zalando" for zalando.co.uk and shop.zalando.de (approximate, no PSL)."""
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else domain


def build_jdm(jdm, records, is_ambiguous, date, version, report):
    sites = read_json(jdm / "_data" / "sites.json")
    notice = (jdm / "LICENSE").read_text(encoding="utf-8").strip()
    by_domain = {}
    by_name = {}
    for record in records:
        for domain in record.get("domains", ()):
            by_domain[domain] = record["slug"]
        for name in [record["name"], *record.get("runs", ())]:
            by_name.setdefault(_normalize_name(name), set()).add(record["slug"])

    def domain_match(host):
        labels = host.split(".")
        for start in range(len(labels) - 1):
            slug = by_domain.get(".".join(labels[start:]))
            if slug:
                return slug
        return None

    records_by_slug = {record["slug"]: record for record in records}
    labels = {}  # slug -> brand labels: base labels of its domains, its name and brands, normalized
    for record in records:
        found = {base_label(d) for d in record.get("domains", ())}
        found |= {_normalize_name(n) for n in [record["name"], *record.get("runs", ())]}
        labels[record["slug"]] = found

    mapped = {}  # slug -> {"name": jdm name, "domains": set}
    sites_mapped = unmatched = ambiguous_sites = 0
    for site in sites:
        if not isinstance(site, dict) or not isinstance(site.get("name"), str):
            continue
        domains = {d for d in (host_domain(x) for x in site.get("domains", []) if isinstance(x, str)) if d}
        # The deletion URL is not used: it is often hosted by a third party (a forum, a help desk).
        by_dom = {s for s in (domain_match(d) for d in domains) if s}
        by_nm = by_name.get(_normalize_name(site["name"]), set())
        if len(by_dom) > 1 or (by_dom and by_nm and not (by_dom & by_nm)):
            ambiguous_sites += 1
            continue
        candidates = by_dom or by_nm
        if len(candidates) != 1:
            if candidates:
                ambiguous_sites += 1
            else:
                unmatched += 1
            continue
        slug = next(iter(candidates))
        record = records_by_slug[slug]
        if not by_dom and (record.get("domains") or "all" not in record.get("relevant-countries", ())):
            # A name match alone is too weak when the record has domains the site does not share,
            # or when the record is one country's branch or licensee of a global brand.
            unmatched += 1
            continue
        sites_mapped += 1
        entry = mapped.setdefault(slug, {"name": site["name"].strip(), "domains": set()})
        # Keep only domains of the record's brand family; a site may list third-party
        # domains (other forums, partner sites).
        entry["domains"] |= {d for d in domains if domain_match(d) == slug or base_label(d) in labels[slug]}

    # A domain that another official record owns, or that two mapped sites share, is dropped,
    # and so is a subdomain of a domain the record already has.
    owner = {}
    for slug, entry in mapped.items():
        for domain in entry["domains"]:
            owner.setdefault(domain, set()).add(slug)
    out = []
    dropped = 0
    for slug in sorted(mapped):
        own = set(records_by_slug[slug].get("domains", ()))
        keep = []
        for domain in sorted(mapped[slug]["domains"], key=lambda d: (d.count("."), d)):
            if domain in own or any(domain.endswith("." + parent) for parent in [*own, *keep]):
                continue
            if is_ambiguous(domain) or len(owner[domain]) > 1 or domain_match(domain) not in (None, slug):
                dropped += 1
                continue
            keep.append(domain)
        if keep:
            name = mapped[slug]["name"]
            if not re.match(r"^\S(.*\S)?$", name):
                name = slug
            out.append({"slug": slug, "name": name, "domains": sorted(keep)})
    report["jdm"] = {
        "sites": len(sites),
        "sites_mapped": sites_mapped,
        "sites_unmatched": unmatched,
        "sites_ambiguous": ambiguous_sites,
        "records": len(out),
        "domains_mapped": sum(len(r["domains"]) for r in out),
        "domains_dropped": dropped,
    }
    sources = [{"name": "jdm-contrib/jdm", "url": "https://github.com/jdm-contrib/jdm", "licence": "MIT"}]
    commit = git_commit(jdm)
    if commit:
        sources[0]["commit"] = commit
    header = {
        "name": "JustDeleteMe domains for the Unlist official Organization List",
        "licence": "MIT",
        "notice": notice,
        "credit": "Domains from JustDeleteMe, https://github.com/jdm-contrib/jdm, mapped onto Unlist slugs.",
        "homepage": HOMEPAGE,
        "version": version,
        "date": date,
        "schema_version": SCHEMA_VERSION,
        "sources": sources,
    }
    return {"header": header, "records": out}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def serialize(document):
    """Compact JSON with one record per line, so upstream bumps can be reviewed as a diff."""
    if not isinstance(document, dict) or "records" not in document:
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    parts = []
    for key, value in document.items():
        if isinstance(value, list):
            body = ",\n".join(dumps(item) for item in value)
            parts.append(f"{dumps(key)}:[\n{body}\n]" if value else f"{dumps(key)}:[]")
        else:
            parts.append(f"{dumps(key)}:{dumps(value)}")
    return "{" + ",\n".join(parts) + "}\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("upstream", type=pathlib.Path, help="checkout of https://github.com/datenanfragen/data")
    parser.add_argument("--jdm", type=pathlib.Path, help="checkout of https://github.com/jdm-contrib/jdm")
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "dist")
    parser.add_argument("--version", help="list version (default: the date as YYYY.MM.DD)")
    parser.add_argument("--date", help="list date, YYYY-MM-DD (default: today)")
    parser.add_argument("--upstream-commit", help="commit of the upstream checkout, if .git cannot be read")
    args = parser.parse_args(argv)
    try:
        outputs, report = build(
            args.upstream, jdm=args.jdm, version=args.version, date=args.date, upstream_commit=args.upstream_commit
        )
    except BuildError as error:
        print("Build failed:", file=sys.stderr)
        for line in error.errors:
            print(f"  {line}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for name, document in outputs.items():
        (args.out / name).write_text(serialize(document), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
