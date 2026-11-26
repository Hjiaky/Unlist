#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
#
# Upgrade test (spec section 17, item 3): install an older version of Unlist, put data into
# it, then run the current version's migrations against the same data directory and check
# that nothing was lost.
#
#   scripts/upgrade-test.sh <old-git-ref>      e.g. scripts/upgrade-test.sh v0.1.0-pre1
#
# Runs without Docker: it uses a git worktree for the old version and the current checkout
# for the new one, each with its own virtual environment.
set -euo pipefail

OLD_REF="${1:?usage: scripts/upgrade-test.sh <old-git-ref>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'git -C "$ROOT" worktree remove --force "$WORK/old" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

export UNLIST_DATA_DIR="$WORK/data" UNLIST_KEY_FILE="$WORK/key/unlist.key"

echo "== Old version: $OLD_REF"
git -C "$ROOT" worktree add --detach "$WORK/old" "$OLD_REF" >/dev/null
python3 -m venv "$WORK/old-venv"
"$WORK/old-venv/bin/pip" install -q -r "$WORK/old/requirements.txt"
(
  cd "$WORK/old"
  "$WORK/old-venv/bin/python" -m unlist.bootstrap
  "$WORK/old-venv/bin/python" manage.py migrate --noinput -v 0
  if "$WORK/old-venv/bin/python" manage.py help load_bundled_lists >/dev/null 2>&1; then
    "$WORK/old-venv/bin/python" manage.py load_bundled_lists -v 0
  fi
  # Put data in with whatever the old version has: always the Operator account, plus a Subject
  # with consent when the subjects app exists.
  "$WORK/old-venv/bin/python" manage.py shell -c "
from django.apps import apps
from django.contrib.auth import get_user_model
get_user_model().objects.create_user('operator', password='a long enough passphrase')
if apps.is_installed('unlist.subjects') and apps.get_containing_app_config('unlist.subjects.models'):
    try:
        from unlist.subjects.models import Mailbox, Subject
        from unlist.subjects.consent import record_consent
        s = Subject.objects.create(name='Upgrade Test', country='DE')
        Mailbox.objects.create(subject=s, email='upgrade@example.org')
        record_consent(s, 'subject')
    except Exception as error:
        print('subjects not usable in the old version:', error)
"
)
mkdir -p "$WORK/data/attachments/upgrade"
echo "kept across the upgrade" > "$WORK/data/attachments/upgrade/marker.txt"

count_rows() {
  "$1" manage.py shell -c "
import json
from django.apps import apps
counts = {m._meta.label: m.objects.count() for m in apps.get_models() if m._meta.app_label in
          ('auth', 'subjects', 'cases', 'mail', 'organizations', 'breaches', 'stats', 'llm', 'core')}
print(json.dumps(counts, sort_keys=True))
"
}

BEFORE="$(cd "$WORK/old" && count_rows "$WORK/old-venv/bin/python" | tail -1)"

echo "== New version: $(git -C "$ROOT" rev-parse --short HEAD)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=python3
(
  cd "$ROOT"
  "$PY" manage.py migrate --noinput -v 0
  "$PY" manage.py load_bundled_lists -v 0
  "$PY" manage.py load_breaches -v 0
  "$PY" manage.py check
)
AFTER="$(cd "$ROOT" && count_rows "$PY" | tail -1)"

python3 -I - "$BEFORE" "$AFTER" <<'EOF'
import json, sys
before, after = json.loads(sys.argv[1]), json.loads(sys.argv[2])
lost = {label: (count, after.get(label)) for label, count in before.items()
        if label not in ("organizations.ListRecord", "organizations.Organization", "organizations.Domain")
        and (after.get(label) or 0) < count}
if lost:
    sys.exit(f"Rows lost in the upgrade: {lost}")
print("Rows kept:", {k: v for k, v in before.items() if v})
EOF

test "$(cat "$WORK/data/attachments/upgrade/marker.txt")" = "kept across the upgrade"
(cd "$ROOT" && "$PY" manage.py shell -c "
from django.contrib.auth import get_user_model
assert get_user_model().objects.get(username='operator').check_password('a long enough passphrase')
")
echo "Upgrade from $OLD_REF passed."
