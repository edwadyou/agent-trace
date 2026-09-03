# -*- coding: utf-8 -*-
# This file was split out of the original ``viewer.py`` single-file app.
# Do not edit by hand where avoidable; keep the module boundaries clean.
from __future__ import annotations

import json
import re

import streamlit as st

from viewer.normalize import canon

from .config import _KNOWN_PAYLOAD_FIELDS, _TOOL_ENVELOPE_RE
from .format import _esc


def _try_parse_json_string(s):

    """If *s* is a JSON string (optionally wrapped in a ```json ... ```

    code fence), return the parsed object; otherwise return None.



    Used to expand inline JSON embedded inside LLM message ``content``

    into a collapsible tree instead of showing it as one raw string.

    """

    if not isinstance(s, str):

        return None

    t = s.strip()

    # strip ```json ... ``` / ``` ... ``` fences

    if t.startswith("```"):

        first_nl = t.find("\n")

        if first_nl >= 0:

            t = t[first_nl + 1:]

        if t.rstrip().endswith("```"):

            t = t.rstrip()[:-3].strip()

        else:

            t = t.strip()

    if not (t.startswith("{") or t.startswith("[")):

        return None

    try:

        return json.loads(t)

    except (json.JSONDecodeError, ValueError):

        return None


def _try_parse_envelope(val):

    """

    Detect a LangGraph-style json\\n{...}\\n envelope and

    return its parsed dict/list, or None on miss.

    """

    if not isinstance(val, str):

        return None

    s = val.strip()

    if not s.startswith("json"):

        return None

    m = _TOOL_ENVELOPE_RE.match(s)

    if m is None:

        return None

    try:

        return json.loads(m.group(1).strip())

    except (json.JSONDecodeError, TypeError, ValueError):

        return None


def _deep_parse_json_strings(obj):
    """Recursively convert JSON-string fields (incl. ```json ... ``` fences)
    inside a parsed payload into real dict/list objects, so the structured
    renderer (and st.json) shows them as collapsible trees instead of raw
    strings with \n escapes.  Non-JSON strings are returned unchanged.
    """
    if isinstance(obj, dict):
        return {k: _deep_parse_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_parse_json_strings(v) for v in obj]
    if isinstance(obj, str):
        parsed = _try_parse_json_string(obj)
        if parsed is not None:
            return parsed
        return obj
    return obj


def _render_structured(obj, *, depth=0):

    """

    Recursively render a parsed JSON payload.

    

    Known payload-array keys (sub_claims, steps, facts, ...)

    are rendered as labelled expanders so long enumerated

    payloads do not flood the page. Each item inside a known

    list is shown as its own expandable card titled by the

    item"s first human-readable field (id / text / name).

    """

    obj = _deep_parse_json_strings(obj)

    if isinstance(obj, dict):

        if not obj:

            st.caption("empty dict")

            return

        known_pairs = [(k, v) for k, v in obj.items() if isinstance(v, list) and k in _KNOWN_PAYLOAD_FIELDS]

        other = {k: v for k, v in obj.items() if not (isinstance(v, list) and k in _KNOWN_PAYLOAD_FIELDS)}

        if other:

            st.json(other)

        for k, v in known_pairs:

            label = str(k) + "  (" + str(len(v)) + " items)"

            with st.expander(label, expanded=False):

                _render_structured(v, depth=depth + 1)

    elif isinstance(obj, list):

        if not obj:

            st.caption("empty list")

            return

        for i, item in enumerate(obj):

            if isinstance(item, dict):

                title = _card_title(item, i + 1)

                with st.expander(title, expanded=False):

                    _render_structured(item, depth=depth + 1)

            elif isinstance(item, (dict, list)):

                _render_structured(item, depth=depth + 1)

            else:

                st.markdown("- " + _esc(str(item)))

    elif isinstance(obj, str):

        st.markdown(_esc(obj))

    else:

        st.write(obj)


def _card_title(item, default_index):

    """Pick a short human-readable title for a dict item card.

    Falls back to #<index> when no obvious label exists.

    """

    if not isinstance(item, dict):

        return "#" + str(default_index)

    for k in ("id", "claim_id", "step", "text", "name", "title", "label"):

        v = item.get(k)

        if isinstance(v, str) and v.strip():

            short = v.strip().replace(chr(10), " ")

            return (str(k) + ": " + short)[:80]

    return "#" + str(default_index)


def _render_input_fallback(attrs, key):

    """Smart fallback for input/output values."""

    # Try flat-key read first (matches the JSONL exporter format), then

    # fall back to canon() so the nested-dict variant works too.

    val = attrs.get(key)

    if val is None:

        val = canon(attrs, key)

    if val is None:

        st.caption(f"（未捕获 {key.split(chr(46))[0]} ）")

        return

    if isinstance(val, str):

        parsed = None

        # Try a LangGraph-style json\n{...}\n envelope first.

        env = _try_parse_envelope(val)

        if isinstance(env, (dict, list)):

            parsed = env

        # Then a plain JSON string fallback.

        if parsed is None:

            try:

                cand = json.loads(val)

                if isinstance(cand, (dict, list)):

                    parsed = cand

            except (json.JSONDecodeError, TypeError, ValueError):

                pass

        if parsed is not None:

            _render_structured(parsed)

        elif len(val) > 800:

            st.code(val[:800])

            st.caption("…（被截断）")

        else:

            st.code(val)

    else:

        if isinstance(val, (dict, list)):

            _render_structured(val)

        else:

            st.json(val)


__all__ = ['_try_parse_json_string', '_try_parse_envelope', '_deep_parse_json_strings', '_render_structured', '_card_title', '_render_input_fallback']
