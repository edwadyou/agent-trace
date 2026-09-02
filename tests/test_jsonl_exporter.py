"""Regression tests for JsonlFileExporter truncate_on_init behaviour."""
from __future__ import annotations
from pathlib import Path

from agent_monitor import jsonl_exporter
from agent_monitor.jsonl_exporter import JsonlFileExporter


def test_default_does_not_truncate(tmp_path: Path):
    "Default truncate_on_init=False preserves pre-existing content."
    f = tmp_path / "x.jsonl"
    f.write_text(chr(123) + chr(34) + "legacy" + chr(34) + ": 1" + chr(125) + chr(10), encoding="utf-8")
    JsonlFileExporter(f)
    assert f.read_text(encoding="utf-8") == chr(123) + chr(34) + "legacy" + chr(34) + ": 1" + chr(125) + chr(10)


def test_explicit_truncate_clears(tmp_path: Path):
    f = tmp_path / "x.jsonl"
    f.write_text(chr(123) + chr(34) + "legacy" + chr(34) + ": 1" + chr(125) + chr(10), encoding="utf-8")
    JsonlFileExporter(f, truncate_on_init=True)
    assert f.read_text(encoding="utf-8") == ""


def test_repeat_construction_does_not_re_truncate(tmp_path: Path):
    "Two JsonlFileExporter on the same file in one process only truncate once."
    f = tmp_path / "x.jsonl"
    JsonlFileExporter(f, truncate_on_init=True)
    f.write_text(chr(123) + chr(34) + "first" + chr(34) + ": 1" + chr(125) + chr(10), encoding="utf-8")
    JsonlFileExporter(f, truncate_on_init=True)
    assert f.read_text(encoding="utf-8") == chr(123) + chr(34) + "first" + chr(34) + ": 1" + chr(125) + chr(10)


def test_registry_is_module_level():
    jsonl_exporter._TRUNCATED_FILES.add("__synthetic_path__")
    assert "__synthetic_path__" in jsonl_exporter._TRUNCATED_FILES
    jsonl_exporter._TRUNCATED_FILES.discard("__synthetic_path__")
