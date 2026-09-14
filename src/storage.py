"""Shared sqlite connection helpers used by both the core runtime and the API presentation layer."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
