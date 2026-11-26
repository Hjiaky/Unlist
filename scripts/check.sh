#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Run every check CI runs; stop at the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
RUFF="${RUFF:-ruff}"
[ -x .venv/bin/ruff ] && RUFF=.venv/bin/ruff
export UNLIST_TESTING=1
"$RUFF" check .
"$RUFF" format --check .
"$PY" manage.py makemigrations --check --dry-run
"$PY" manage.py test
"$PY" manage.py check_licences
echo "All checks passed."
