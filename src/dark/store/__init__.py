"""Aggregate store (goal 017; decisions E2, E10 and E14).

Numbers of each session, inventory snapshot and collection, kept outside
the transcripts in an SQLite file, so that the audit can compare a week
with the previous one after Claude Code deletes the transcripts.

Self-contained: standard library only, and no import of other `dark`
modules. The collection command (a later goal) turns the reader's sessions
into the records of `records.py`.
"""

from . import schema
from .core import DEFAULT_TIMEOUT, AggregateStore, open_store
from .errors import (MigrationError, RepositoryConflict, SchemaError, StoreCorrupt,
                     StoreError, StoreLocationError, StoreLocked, StoreTooNew,
                     UnknownRepository)
from .kinds import NAME_MAX
from .paths import default_data_dir, default_store_path
from .queries import (InventoryDiff, InventoryEntry, InventoryKey, Median, PartKey,
                      SizeChange, UnusedStreak, UsageChanges, WeekComparison, WeekSummary)
from .records import (LINK_KINDS, PART_KINDS, CollectionRecord, CommitLink, HookOutcome,
                      InventoryItem, InventorySnapshot, PartUsage, PermissionModeCount,
                      RepositoryRecord, SessionRecord, TokenCounts)
from .schema import SCHEMA_VERSION
from .weeks import IsoWeek

__all__ = [
    "AggregateStore", "open_store", "DEFAULT_TIMEOUT", "SCHEMA_VERSION", "NAME_MAX",
    "default_data_dir", "default_store_path", "schema",
    "StoreError", "SchemaError", "RepositoryConflict", "UnknownRepository",
    "StoreLocationError", "StoreLocked", "StoreCorrupt", "StoreTooNew", "MigrationError",
    "SessionRecord", "TokenCounts", "PermissionModeCount", "HookOutcome", "PartUsage",
    "CommitLink", "RepositoryRecord", "InventoryItem", "InventorySnapshot",
    "CollectionRecord", "PART_KINDS", "LINK_KINDS",
    "IsoWeek", "WeekSummary", "WeekComparison", "Median", "PartKey", "UsageChanges",
    "UnusedStreak", "InventoryKey", "InventoryEntry", "SizeChange", "InventoryDiff",
]
