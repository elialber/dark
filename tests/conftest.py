"""Shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_default_store(tmp_path_factory, monkeypatch):
    """No test reads or writes the user's real aggregate store (goal 027)."""
    from dark import cli
    path = tmp_path_factory.mktemp("default-store") / "aggregates.sqlite3"
    monkeypatch.setattr(cli, "default_store_path", lambda *a, **k: path)
