from __future__ import annotations

import importlib.metadata

from agent_monitor.monitor import _auto_instrument


class FakeEntryPoint:
    def __init__(self, name, factory):
        self.name = name
        self._factory = factory

    def load(self):
        return self._factory


class FakeEntryPoints:
    def __init__(self, entries):
        self._entries = entries

    def select(self, *, group):
        assert group == "openinference_instrumentor"
        return self._entries


class FakeInstrumentor:
    def __init__(self, events, name):
        self.events = events
        self.name = name

    def instrument(self, tracer_provider):
        self.events.append(("instrument", self.name, tracer_provider))


def _install_fake_entry_points(monkeypatch, names):
    events = []
    entries = [
        FakeEntryPoint(name, lambda name=name: FakeInstrumentor(events, name))
        for name in names
    ]
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda: FakeEntryPoints(entries),
    )
    return events


def test_requested_instrumentor_matches_short_or_full_entry_point_name(
    monkeypatch, capsys
):
    events = _install_fake_entry_points(
        monkeypatch,
        ["openinference-instrumentation-langchain"],
    )
    provider = object()
    installed = _auto_instrument(
        tracer_provider=provider,
        instrumentors=["langchain"],
    )

    assert len(installed) == 1
    assert events == [("instrument", "openinference-instrumentation-langchain", provider)]
    assert "requested instrumentors not installed" not in capsys.readouterr().err


def test_missing_requested_instrumentor_always_warns(monkeypatch, capsys):
    _install_fake_entry_points(monkeypatch, ["langchain"])

    installed = _auto_instrument(
        tracer_provider=object(),
        instrumentors=["langchain", "openai"],
        verbose=False,
    )

    assert len(installed) == 1
    err = capsys.readouterr().err
    assert "requested instrumentors not installed: openai" in err


def test_empty_instrumentor_list_activates_none(monkeypatch, capsys):
    events = _install_fake_entry_points(monkeypatch, ["langchain"])

    installed = _auto_instrument(
        tracer_provider=object(),
        instrumentors=[],
    )

    assert installed == []
    assert events == []
    assert capsys.readouterr().err == ""
