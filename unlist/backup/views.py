# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from unlist.backup import service


@login_required
@require_GET
def overview(request):
    last = service.last_backup()
    return render(request, "backup/overview.html", {"last_backup": last[0] if last else None})


@login_required
@require_POST
def download(request):
    """Create a fresh archive (a copy stays in DATA_DIR/backups) and stream it."""
    archive = service.create_backup()
    response = FileResponse(
        open(archive, "rb"), as_attachment=True, filename=archive.name, content_type="application/gzip"
    )
    response["Cache-Control"] = "no-store"
    return response
