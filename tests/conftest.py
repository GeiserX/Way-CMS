"""Conftest for Way-CMS tests.

The production code uses get_db() which opens a new connection each time.
This causes issues in tests because nested calls (e.g. create() calling get_by_id())
open separate connections and the inner one can't see uncommitted data from the outer.

We fix this by patching get_db to always return the same shared connection.
"""

import os
import sys
import sqlite3
from contextlib import contextmanager

import pytest

# Add cms directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cms'))


@pytest.fixture(autouse=True)
def shared_db(tmp_path, monkeypatch):
    """Patch database module to use a shared in-memory-like connection."""
    data_dir = str(tmp_path / "data")
    db_path = os.path.join(data_dir, "waycms.db")
    os.makedirs(data_dir, exist_ok=True)

    monkeypatch.setattr('database.DATA_DIR', data_dir)
    monkeypatch.setattr('database.DB_PATH', db_path)

    # Create a single shared connection
    shared_conn = sqlite3.connect(db_path)
    shared_conn.row_factory = sqlite3.Row
    shared_conn.execute("PRAGMA foreign_keys = ON")

    @contextmanager
    def shared_get_db():
        try:
            yield shared_conn
            shared_conn.commit()
        except Exception:
            shared_conn.rollback()
            raise

    monkeypatch.setattr('database.get_db', shared_get_db)

    # Also patch in models and auth since they import get_db at module level
    import database
    import models
    import auth

    # Patch get_db in models module (it imports from database)
    monkeypatch.setattr('models.get_db', shared_get_db)

    # Initialize the database schema
    database.init_db()

    yield shared_conn

    shared_conn.close()
