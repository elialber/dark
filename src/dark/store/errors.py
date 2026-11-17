"""Errors raised by the aggregate store. Each message says what to do next."""

from __future__ import annotations


class StoreError(Exception):
    """Base class for every error of the aggregate store."""


class SchemaError(StoreError, ValueError):
    """A value or field outside the declared schema (E14)."""


class RepositoryConflict(SchemaError):
    """Root commits that already belong to two different repositories."""


class UnknownRepository(StoreError, LookupError):
    """A session or snapshot points to a repository that was never written."""


class StoreLocationError(StoreError):
    """The store would live inside an audited repository."""


class StoreLocked(StoreError):
    """Another process holds the write lock for longer than the timeout."""


class StoreCorrupt(StoreError):
    """The file is not a readable aggregate store."""


class StoreTooNew(StoreError):
    """The file was written by a newer version of the code."""


class MigrationError(StoreError):
    """A forward migration could not be applied; the file was left as it was."""
