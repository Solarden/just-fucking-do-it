"""Shared test fixtures -- fresh temp DB for each test."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from jfdi import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path):
    """Create a fresh SQLite DB in a temp directory for each test."""
    db_path = tmp_path / "test_jfdi.db"
    db.set_db_path(db_path)
    db.init_db()
    yield db_path
    db.set_db_path(None)
