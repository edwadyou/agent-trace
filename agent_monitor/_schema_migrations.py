"""JSONL trace schema migration.

Upgrades a v1.0.0 record to the current schema in-place. Idempotent: if the
record already declares the current ``schema_version``, the original dict is
returned untouched.

This module is the *only* place that knows how to read older schemas. Producers
(JsonlFileExporter) write the current version. Consumers (viewer.py,
render.py, etc.) call ``migrate(record)`` before parsing fields that did not
exist in older versions.
"""
from __future__ import annotations
from typing import Any

# Re-export so callers can rely on a single source of truth.
from .jsonl_exporter import SCHEMA_VERSION  # noqa: F401


def migrate(record: dict[str, Any], from_version: str | None = None) -> dict[str, Any]:
    """Return a record whose schema matches the SDK's current SCHEMA_VERSION.

    Args:
        record: one parsed JSONL row (a dict).
        from_version: optional override. If omitted, the function reads
            ``record.get("schema_version", "1.0.0")``.

    Notes:
        - Migrations are *additive*: missing fields are filled with sensible
          defaults; existing fields are NEVER overwritten.
        - Records already at the current version are returned unchanged.
        - Records from a *future* (newer) schema are passed through with
          their original ``schema_version`` preserved, so forward-compatible
          fields are not silently lost by an older SDK reading a newer file.
    """
    current = str(record.get("schema_version") or from_version or "1.0.0")
    if current == SCHEMA_VERSION:
        return record

    # 1.0.0 -> 1.1.0: add schema_version + service_name
    if current == "1.0.0":
        record = _migrate_1_0_to_1_1(record)
        current = SCHEMA_VERSION
    # Future migrations append here as ``elif current == "1.1.0": ...``

    # Forward-compatibility: a record from a *newer* schema than what this
    # SDK knows about must NOT be silently downgraded. Pass it through with
    # its original ``schema_version`` so newer fields are preserved for the
    # consumer; only fill in defaults for fields THIS schema guarantees.
    if record.get("schema_version") and record["schema_version"] != SCHEMA_VERSION:
        record.setdefault("service_name", None)
        return record

    record["schema_version"] = SCHEMA_VERSION
    return record


def _migrate_1_0_to_1_1(rec: dict[str, Any]) -> dict[str, Any]:
    rec.setdefault("schema_version", SCHEMA_VERSION)
    rec.setdefault("service_name", None)
    return rec