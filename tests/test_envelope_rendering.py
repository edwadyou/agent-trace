"""Regression tests for the JSON envelope + structured renderer.

NOTE: these tests used to read the single-file ``viewer.py``. The viewer was
split into the ``viewer_app`` package, so they now read the module that owns
each construct (``structured.py`` / ``msg.py`` / ``config.py``) and pull the
function source via ``inspect`` so they do not depend on file formatting.
"""
from __future__ import annotations
import inspect
import json

from viewer_app import msg as msg_mod
from viewer_app import structured as structured_mod
from viewer_app.config import _KNOWN_PAYLOAD_FIELDS, _TOOL_ENVELOPE_RE


def _fn_src(func) -> str:
    return inspect.getsource(func)


def test_render_structured_known_field_keys_covered():
    for k in ("sub_claims", "claims", "subclaims", "steps", "facts",
              "items", "results", "documents", "sources", "evidence",
              "todos", "checklist"):
        assert k in _KNOWN_PAYLOAD_FIELDS, f"{k!r} missing from _KNOWN_PAYLOAD_FIELDS"


def test_input_fallback_wired_with_envelope_parser():
    body = _fn_src(structured_mod._render_input_fallback)
    assert "env = _try_parse_envelope(val)" in body
    assert "_render_structured(parsed)" in body


def test_render_msg_str_branch_envelope_then_fence():
    body = _fn_src(msg_mod._render_msg)
    assert "_env = _try_parse_envelope(content_val)" in body
    assert "_env = _try_parse_json_string(content_val)" in body
    assert "_render_structured(_env)" in body


def test_render_msg_text_part_uses_envelope():
    body = _fn_src(msg_mod._render_msg)
    assert "_env = _try_parse_envelope(_part)" in body
    assert "_render_structured(_env)" in body


def test_envelope_regex_matches_typical_payload():
    """The installed _TOOL_ENVELOPE_RE matches a real-world LangGraph payload."""
    rx = _TOOL_ENVELOPE_RE

    # Build a sample with REAL newline chars so the regex sees them.
    nl = "\n"
    sample = (
        "json" + nl
        + "{" + nl
        + '  "sub_claims": [' + nl
        + '    {"id": "1", "text": "Acme"},' + nl
        + '    {"id": "2", "text": "Beta"}' + nl
        + "  ]" + nl
        + "}" + nl
    )
    m = rx.match(sample.strip())
    assert m is not None, "envelope regex must match the typical payload"
    inner = json.loads(m.group(1).strip())
    assert "sub_claims" in inner
    assert len(inner["sub_claims"]) == 2


def test_envelope_regex_rejects_non_json_prefix():
    rx = _TOOL_ENVELOPE_RE
    assert rx.match("not_json") is None
    assert rx.match("javascript:foo") is None
    assert rx.match("json") is None


def test_envelope_helper_roundtrips_via_parser():
    """`_try_parse_envelope` accepts the payload the regex was built for and
    rejects anything that merely starts with the word `json`."""
    payload = "json\n{\"sub_claims\": [{\"id\": \"1\"}]}\n"
    assert structured_mod._try_parse_envelope(payload) == {"sub_claims": [{"id": "1"}]}
    assert structured_mod._try_parse_envelope("json") is None
    assert structured_mod._try_parse_envelope("just text") is None
    assert structured_mod._try_parse_envelope(None) is None


def test_card_title_picks_human_field():
    body = _fn_src(structured_mod._card_title)
    assert "def _card_title(item, default_index):" in body
    for k in ("id", "claim_id", "step", "text", "name", "title", "label"):
        assert ('"' + k + '"') in body


def test_envelope_helper_present_in_module():
    """Both _try_parse_envelope and _render_structured are defined as module-level
    callables (not local to a nested function)."""
    assert callable(structured_mod._try_parse_envelope)
    assert callable(structured_mod._render_structured)
    # The recursive renderer must handle dict, list, and string branches.
    body = _fn_src(structured_mod._render_structured)
    assert "if isinstance(obj, dict):" in body
    assert "elif isinstance(obj, list):" in body
    assert "elif isinstance(obj, str):" in body
