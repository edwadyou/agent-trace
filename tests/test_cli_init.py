from __future__ import annotations

from pathlib import Path

import agent_monitor.__main__ as cli


def _run_init(monkeypatch, tmp_path, *framework_args: str):
    calls: dict[str, list] = {
        "extras": [],
        "streamlit": [],
        "sdks": [],
    }

    monkeypatch.setattr(cli, "_agent_monitor_importable", lambda: True)
    monkeypatch.setattr(
        cli, "_pip_install_extras", lambda frameworks: calls["extras"].append(list(frameworks)) or 0
    )
    monkeypatch.setattr(
        cli,
        "_pip_install_framework_sdks",
        lambda frameworks: calls["sdks"].append(list(frameworks)) or 0,
    )
    monkeypatch.setattr(
        cli, "_pip_install_streamlit", lambda: calls["streamlit"].append(True) or 0
    )
    monkeypatch.setattr(
        "agent_monitor._detect.detect_compatible",
        lambda candidates=None: list(candidates or []),
    )

    out = Path(tmp_path) / "instrument.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc = cli.main(["init", *framework_args, "--out", str(out)])
    return rc, out, calls


def test_parse_frameworks_expands_alias_and_deduplicates_in_stable_order():
    assert cli._parse_frameworks("langchain_openai") == ["langchain", "openai"]
    assert cli._parse_frameworks("openai,langchain,openai") == ["langchain", "openai"]
    assert cli._parse_frameworks("pure") == []


def test_auto_init_combines_detected_frameworks_and_writes_one_call(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "agent_monitor._detect.detect_installed_frameworks",
        lambda: ["openai", "langchain"],
    )
    rc, out, calls = _run_init(
        monkeypatch,
        tmp_path,
        "--framework",
        "auto",
        "--no-install-streamlit",
    )

    assert rc == 0
    assert calls["extras"] == [["langchain", "openai"]]
    assert calls["sdks"] == []
    assert calls["streamlit"] == []
    assert 'INSTRUMENTORS = ["langchain", "openai"]' in out.read_text(encoding="utf-8")


def test_explicit_comma_and_alias_generate_the_same_framework_list(monkeypatch, tmp_path):
    rc, out, _ = _run_init(
        monkeypatch,
        tmp_path,
        "--framework",
        "langchain,openai",
        "--no-install-streamlit",
    )
    assert rc == 0
    assert 'INSTRUMENTORS = ["langchain", "openai"]' in out.read_text(encoding="utf-8")

    rc, out, _ = _run_init(
        monkeypatch,
        tmp_path / "alias",
        "--framework",
        "langchain_openai",
        "--no-install-streamlit",
    )
    assert rc == 0
    assert 'INSTRUMENTORS = ["langchain", "openai"]' in out.read_text(encoding="utf-8")


def test_pure_init_skips_extras_and_no_install_deps_skips_all_pip(monkeypatch, tmp_path):
    rc, out, calls = _run_init(
        monkeypatch,
        tmp_path,
        "--framework",
        "pure",
        "--no-install-streamlit",
    )
    assert rc == 0
    assert calls == {"extras": [], "streamlit": [], "sdks": []}
    assert "INSTRUMENTORS = []" in out.read_text(encoding="utf-8")

    rc, _, calls = _run_init(
        monkeypatch,
        tmp_path / "offline",
        "--framework",
        "langchain,openai",
        "--no-install-deps",
        "--no-install-streamlit",
    )
    assert rc == 0
    assert calls == {"extras": [], "streamlit": [], "sdks": []}


def test_unknown_framework_is_rejected_without_writing_a_file(monkeypatch, tmp_path, capsys):
    rc, out, calls = _run_init(
        monkeypatch,
        tmp_path,
        "--framework",
        "not-a-framework",
        "--no-install-streamlit",
    )
    assert rc == 2
    assert not out.exists()
    assert calls == {"extras": [], "streamlit": [], "sdks": []}
    assert "unknown framework" in capsys.readouterr().out


def test_extras_spec_uses_local_path_as_editable(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_local_project_root", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(
        cli,
        "_pip_install",
        lambda pkgs, *, label, editable=False: calls.append((pkgs, editable)) or 0,
    )

    assert cli._pip_install_extras(["langchain", "openai"]) == 0
    assert calls == [([f"{tmp_path}[langchain,openai]"], True)]


def test_extras_spec_uses_package_name_when_installed(monkeypatch):
    monkeypatch.setattr(cli, "_local_project_root", lambda: None)
    calls = []
    monkeypatch.setattr(
        cli,
        "_pip_install",
        lambda pkgs, *, label, editable=False: calls.append((pkgs, editable)) or 0,
    )

    assert cli._pip_install_extras(["langchain", "openai"]) == 0
    assert calls == [(["agent-monitor[langchain,openai]"], False)]


def test_render_instrument_template_replaces_placeholder_once():
    rendered = cli._render_instrument_template(["langchain", "openai"])
    assert 'INSTRUMENTORS = ["langchain", "openai"]' in rendered
    assert cli._FRAMEWORK_PLACEHOLDER not in rendered


def test_rendered_template_creates_one_agent_root_span():
    "The scaffold must ship the root span, not just the monitor() shell."
    rendered = cli._render_instrument_template(["langchain", "openai"])

    assert "ROOT_SPAN =" in rendered
    assert ") as tracer:" in rendered
    assert "tracer.start_as_current_span(" in rendered
    assert '"openinference.span.kind": "AGENT"' in rendered
    assert "root.set_status(Status(StatusCode.OK))" in rendered
