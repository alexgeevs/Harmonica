"""Test isolation: never touch the real library database.

The app derives its SQLite path from ``HARMONICA_HOME`` (default ``.harmonica``)
and binds the engine at import time in ``harmonica.db``. Running the suite used
to write into the developer's real ``.harmonica/harmonica.db`` and pollute the
~250-song library. We fix that here by pointing ``HARMONICA_HOME`` at a fresh
throwaway directory *before any harmonica module is imported* — pytest loads
conftest.py first, so the module-level engine binds to the temp DB instead.

Tests are self-seeding (they create the rows they need), so an empty DB is fine.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

# Must run at import time, before harmonica.db is first imported below.
_TEST_HOME = tempfile.mkdtemp(prefix="harmonica-tests-")
os.environ["HARMONICA_HOME"] = _TEST_HOME
# Drop any inherited absolute DB URL so it can't override the temp home.
os.environ.pop("HARMONICA_DATABASE_URL", None)


@atexit.register
def _cleanup_test_home() -> None:
    shutil.rmtree(_TEST_HOME, ignore_errors=True)
