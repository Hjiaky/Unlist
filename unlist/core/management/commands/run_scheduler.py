# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import signal
import threading

from django.core.management.base import BaseCommand
from django.utils import timezone

from unlist.core import scheduler


class Command(BaseCommand):
    help = "Run Unlist's scheduler: prepares work on a fixed interval and never sends anything."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run every job once and exit.")
        parser.add_argument("--interval", type=int, default=60, help="Seconds between runs.")

    def handle(self, *args, once=False, interval=60, **options):
        if once:
            self._tick()
            return

        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())

        self.stdout.write(f"Unlist scheduler running every {interval}s with {len(scheduler.JOBS)} job(s).")
        while not stop.is_set():
            self._tick()
            stop.wait(interval)
        self.stdout.write("Unlist scheduler stopped.")

    def _tick(self):
        for name, result in scheduler.run_once(timezone.now()).items():
            if result:
                self.stdout.write(f"{name}: {result}")
