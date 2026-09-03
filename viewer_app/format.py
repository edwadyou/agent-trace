# -*- coding: utf-8 -*-
# This file was split out of the original ``viewer.py`` single-file app.
# Do not edit by hand where avoidable; keep the module boundaries clean.
from __future__ import annotations

import html
import time as _time
from typing import Any

from viewer.canonical import SPAN_KINDS, COLORS
from viewer.normalize import canon, friendly_name, span_kind

from .config import _COST_PER_1K


def _esc(s: Any) -> str:

    if s is None:

        return ""

    return html.escape(str(s), quote=True)


def _format_tokens(n: Any) -> str:

    if n is None:

        return "-"

    try:

        n = int(n)

    except (TypeError, ValueError):

        return str(n)

    if n < 1000:

        return f"{n}"

    if n < 10_000:

        return f"{n / 1000:.1f}k"

    return f"{n / 1000:.0f}k"


def _format_duration_ms(ms: float) -> str:

    if ms is None:

        return "-"

    if ms >= 60_000:

        return f"{ms / 60_000:.1f}m"

    if ms >= 1000:

        return f"{ms / 1000:.2f}s"

    return f"{ms:.0f}ms"


def _format_ts(ns: int) -> str:

    if not ns:

        return "-"

    try:

        return _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ns / 1_000_000_000))

    except (OSError, ValueError, OverflowError):

        return str(ns)


def _format_ts_ms(ns: int) -> str:

    """Same as _format_ts but includes milliseconds."""

    if not ns:

        return "-"

    try:

        s = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ns / 1_000_000_000))

        ms = (ns // 1_000_000) % 1000

        return f"{s}.{ms:03d}"

    except (OSError, ValueError, OverflowError):

        return str(ns)


def _status_label(status: str) -> str:

    s = (status or "").upper()

    if s == "OK":

        return ("OK", "ok")

    if s == "ERROR":

        return ("ERROR", "err")

    return ("UNSET", "unset")


def _kind_pill_html(kind: str) -> str:

    info = SPAN_KINDS.get(kind, SPAN_KINDS["UNKNOWN"])

    icon, color_name, label = info

    color = COLORS.get(color_name, "#6b7280")

    return (

        f'<span class="kind-pill" style="background:{color}">'

        f'{_esc(icon)} {_esc(label)}</span>'

    )


def _span_kind_icon(kind: str) -> str:

    info = SPAN_KINDS.get(kind, SPAN_KINDS["UNKNOWN"])

    return info[0]


def _span_display_name(span: dict) -> str:

    attrs = span.get("attributes") or {}

    kind = span_kind(attrs)

    disp, _ = friendly_name(span.get("name", ""), kind)

    if kind == "TOOL":

        tn = canon(attrs, "tool.name")

        if tn:

            return f"{tn}"

    if kind == "LLM":

        m = canon(attrs, "model")

        if m:

            return f"{m}"

    return disp or span.get("name", "(unnamed)")


def _estimate_cost(span: dict) -> float | None:

    """Return USD estimate for an LLM span, or None if unknown.



    Looks up canonical token counts (``canon(attrs, 'tokens.input')`` and

    ``canon(attrs, 'tokens.output')``) and multiplies by the per-1k rate

    for the (provider, model) pair. The previous implementation tried

    an ``attr_key`` prefix (``"tokens." + ".tokens.input"``) that no

    caller ever populated correctly; the dead branch has been removed.

    """

    attrs = span.get("attributes") or {}

    model = canon(attrs, "model") or ""

    provider = (canon(attrs, "model.provider") or "").lower()

    model_l = model.lower()

    rates = _COST_PER_1K.get((provider, model_l))

    if rates is None:

        # Fallback: match by model only (provider unknown in some traces)

        for (prov, m), r in _COST_PER_1K.items():

            if m == model_l:

                rates = r

                break

    if rates is None:

        return None

    tin = canon(attrs, "tokens.input")

    tout = canon(attrs, "tokens.output")

    if not isinstance(tin, int) and not isinstance(tout, int):

        return None

    cost_in  = (tin  or 0) / 1000.0 * rates[0]

    cost_out = (tout or 0) / 1000.0 * rates[1]

    return round(cost_in + cost_out, 4)


__all__ = ['_esc', '_format_tokens', '_format_duration_ms', '_format_ts', '_format_ts_ms', '_status_label', '_kind_pill_html', '_span_kind_icon', '_span_display_name', '_estimate_cost']
