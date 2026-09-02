"""Regression tests for _load_dotenv()."""
from __future__ import annotations
import importlib, os
from pathlib import Path

def _reload_monitor_with_cwd(cwd):
    import pathlib, sys
    real = pathlib.Path.cwd
    pathlib.Path.cwd = classmethod(lambda cls: cwd)
    try:
        name = "agent_monitor.monitor"
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            __import__(name)
        return sys.modules[name]
    finally:
        pathlib.Path.cwd = real


def test_zero_env_value_preserved(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("FEATURE_X=1\n", encoding="utf-8")
    monkeypatch.setenv("FEATURE_X", "0")
    mod = _reload_monitor_with_cwd(tmp_path)
    mod._load_dotenv()
    assert os.environ.get("FEATURE_X") == "0"


def test_dotenv_fills_missing(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("NEW_KEY=hello\n", encoding="utf-8")
    monkeypatch.delenv("NEW_KEY", raising=False)
    mod = _reload_monitor_with_cwd(tmp_path)
    mod._load_dotenv()
    assert os.environ.get("NEW_KEY") == "hello"
