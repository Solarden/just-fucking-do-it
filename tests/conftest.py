"""Shared test fixtures -- fresh temp DB for each test."""

from __future__ import annotations

from pathlib import Path

import pytest

from jfdi import db, service
from jfdi.db import Database


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path):
    """Create a fresh, isolated Database instance for each test."""
    database = Database(tmp_path / "test_jfdi.db")
    database.init_db()
    # Inject into the service layer so service functions use this DB.
    service.set_database(database)
    # Also set the module-level default so test_db.py (which calls
    # db.get_conn() directly) still works.
    db.set_db_path(database.path)
    yield database
    service.set_database(None)
    db.set_db_path(None)
