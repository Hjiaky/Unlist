# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UNLIST_DATA_DIR=/data \
    UNLIST_KEY_FILE=/key/unlist.key

RUN useradd --system --uid 1000 --home-dir /app unlist \
 && mkdir -p /app /data /key

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=unlist:unlist . .
RUN UNLIST_TESTING=1 python manage.py collectstatic --noinput \
 && chmod +x docker/entrypoint.sh

# The entrypoint starts as root only to fix ownership of the two volumes, then drops to `unlist`.
EXPOSE 8000
VOLUME ["/data", "/key"]
ENTRYPOINT ["/app/docker/entrypoint.sh"]
