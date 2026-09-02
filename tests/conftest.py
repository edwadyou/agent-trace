# Pytest configuration: clears the per-process truncation
# registry before every test so file-state cannot leak.
from __future__ import annotations
import pytest

from agent_monitor import jsonl_exporter


@pytest.fixture(autouse=True)
def _reset_jsonl_registry():
    jsonl_exporter._TRUNCATED_FILES.clear()
    yield
    jsonl_exporter._TRUNCATED_FILES.clear()
