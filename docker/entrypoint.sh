#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
#
# One container, two processes: the web server and the scheduler (ADR 0001).
# If either stops, the container stops, so the Operator's restart policy brings both back.
set -euo pipefail

# Docker creates missing bind-mount folders owned by root. Hand them to the unprivileged
# `unlist` user, then continue as that user; nothing below runs as root.
if [ "$(id -u)" = "0" ] && id unlist >/dev/null 2>&1; then
  for dir in "${UNLIST_DATA_DIR:-/data}" "$(dirname "${UNLIST_KEY_FILE:-/key/unlist.key}")"; do
    mkdir -p "$dir"
    chown unlist:unlist "$dir"
  done
  exec setpriv --reuid=unlist --regid=unlist --init-groups "$0" "$@"
fi

python -m unlist.bootstrap
python manage.py migrate --noinput
python manage.py load_bundled_lists   # bundled Organization Lists; local files only

if [ "$#" -gt 0 ]; then
  exec "$@"   # e.g. `docker compose run --rm unlist python manage.py changepassword`
fi

python manage.py run_scheduler &
gunicorn unlist.wsgi:application \
  --bind "0.0.0.0:${UNLIST_PORT:-8000}" \
  --workers "${UNLIST_WORKERS:-2}" \
  --access-logfile - &

trap 'kill -TERM $(jobs -p) 2>/dev/null' TERM INT
wait -n
status=$?
kill -TERM $(jobs -p) 2>/dev/null || true
wait
exit "$status"
