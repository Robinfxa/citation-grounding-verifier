"""Safe phase timing for unmodified CLI subprocesses, without HTTP substitutes."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# The application has a 30-second operation budget; process startup/imports
# precede it. This harness bound must not be shorter than the app's own bound.
PROCESS_TIMEOUT_SECONDS = 35


def install():
    path = Path(os.environ["PROVIDER_PROBE_PHASE_FILE"])

    def phase(name):
        with path.open("a") as stream:
            stream.write(json.dumps({"phase": name, "time": time.monotonic()}) + "\n")

    phase("python_ready")
    import grounding.codex_auth as auth

    phase("auth_imported")
    original_main = auth.main

    def main():
        phase("main_enter")
        try:
            return original_main()
        finally:
            phase("main_exit")

    auth.main = main
