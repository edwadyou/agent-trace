"""Streamlit viewer for ``latest_traces.jsonl`` - Agent Trace Monitor.

Three-column layout
-------------------

    +--------------------------------------------------------+
    |  HEADER  title | trace source picker | trace switcher  |
    +--------------+--------------------------+--------------+
    |  TREE        |  DETAIL                  |  METADATA    |
    |  (left)      |  (center, large)         |  (right)     |
    |              |                          |              |
    |  hierarchical|  [Run][Feedback][Meta]   |  Trace:      |
    |  fold/expand |   Run tab:               |   start/end  |
    |  icon+name+  |    - Input (collapse)    |   duration   |
    |  duration    |    - Output (collapse)   |   tokens     |
    |  click=select|    - Flow state          |   status     |
    |              |   Feedback: scores       |   cost (est.)|
    |              |   Metadata: attrs/events |              |
    |              |                          |  Selected    |
    |              |                          |   span stats |
    +--------------+--------------------------+--------------+

Run tab
    The primary view: collapsible Input + Output blocks showing messages,
    tool calls, return content, and a "flow state" event log.

Feedback tab
    Empty-state friendly; will populate once feedback scores are recorded
    alongside the trace.

Metadata tab
    Full attribute dump, raw attributes, span events.

Trace source auto-discovery
    If TRACE_FILE env var is set, use it. Otherwise, scan a list of
    well-known paths so the UI works out of the box for the common
    ``D:/agent/complex-agent-langchain/`` layout.
"""
from __future__ import annotations

import html
import json
import re
import os
import time as _time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import streamlit as st
import streamlit.components.v1 as components

from viewer.canonical  import SPAN_KINDS, COLORS
from viewer.normalize  import canon, friendly_name, span_kind, to_messages
from viewer.visibility import is_span_visible, filter_visible_attrs


# Bidirectional mermaid-flowchart component (click a span node -> the detail
# column updates WITHOUT a full-page reload).  The frontend lives in
# flowchart_component/ and talks back through the v1 component postMessage
# protocol; the click handler sets Streamlit.setComponentValue which triggers
# a normal (no-navigation) rerun.
_COMPONENT_DIR = Path(__file__).resolve().parent / "flowchart_component"
if (_COMPONENT_DIR / "index.html").is_file():
    _flowchart_component = components.declare_component(
        "agent_flowchart", path=str(_COMPONENT_DIR)
    )
else:
    _flowchart_component = None


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
REFRESH_MS = int(os.environ.get("REFRESH_MS", "3000"))

# Debug-log toggle for the v3-3col viewer pipeline.
# Set DEBUG_V3 = True to re-enable the [viewer.py v3-3col] stderr lines.
DEBUG_V3 = False
def _dbg(msg: str) -> None:
    if not DEBUG_V3:
        return
    import sys as _sys_dbg
    _sys_dbg.stderr.write(f"[viewer.py v3-3col] {msg}\n")
    _sys_dbg.stderr.flush()

try:
    from agent_monitor._schema_migrations import (
        migrate as _migrate_record,
        SCHEMA_VERSION as _SDK_SCHEMA,
    )
except Exception:
    _migrate_record = None
    _SDK_SCHEMA = "unknown"

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_MS, limit=None, key="auto_refresh")
    _autokind = "streamlit-autorefresh"
except ImportError:
    import streamlit.components.v1 as components
    _autokind = "iframe-poll"
    components.html(
        "<script>setTimeout(function(){window.parent.location.reload();}, "
        + str(REFRESH_MS) + ");</script>",
        height=0,
    )

st.set_page_config(
    page_title="Agent Trace Monitor",
    page_icon="\U0001F50E",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Custom CSS - 3-column layout, dark, dense, monospaced data
# ---------------------------------------------------------------------------
_CSS = """
<style>
.block-container { padding-top: 1.6rem; padding-bottom: 1.2rem; max-width: 100%; }
h1, h2, h3, h4 { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
code, pre, .stCode, .stMarkdown code { font-family: ui-monospace, "JetBrains Mono", "Cascadia Code", Consolas, monospace; }

/* ----- layout ----- */
.three-col { display: grid; gap: 12px; }

/* ----- left navigation tree ----- */
.tree-wrap {
    background: rgba(0,0,0,0.22);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 8px 6px 8px 6px;
    max-height: 78vh;
    overflow-y: auto;
}
.tree-row {
    display: grid;
    grid-template-columns: 18px 1fr 70px;
    align-items: center;
    gap: 4px;
    padding: 3px 6px;
    border-radius: 4px;
    margin: 1px 0;
    min-height: 26px;
    border: 1px solid transparent;
}
.tree-row:hover { background: rgba(255,255,255,0.04); }
.tree-row.tree-selected {
    background: rgba(59,130,246,0.18);
    border-color: rgba(59,130,246,0.55);
}
.tree-row.tree-error { border-left: 3px solid #ef4444; padding-left: 3px; }
.tree-row .tree-status { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.tree-row .tree-name {
    display: flex; align-items: center; gap: 6px;
    font-size: 12.5px; color: #e5e7eb;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tree-row .tree-name .tree-name-text {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tree-row .tree-dur {
    font-size: 10.5px; color: #9ca3af;
    font-variant-numeric: tabular-nums;
    text-align: right; padding-right: 2px;
}
.tree-row .tree-chev {
    background: transparent; border: none; cursor: pointer;
    color: #9ca3af; font-size: 10px;
    width: 18px; height: 18px;
    display: flex; align-items: center; justify-content: center;
    padding: 0;
}
.tree-row .tree-chev:hover { color: #e5e7eb; }

/* compact buttons inside tree */
.tree-row .stButton button {
    padding: 2px 6px !important;
    font-size: 11.5px !important;
    line-height: 1.1 !important;
    min-height: 22px !important;
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}
.tree-row.tree-selected .stButton button {
    background: rgba(59,130,246,0.35) !important;
    border-color: rgba(59,130,246,0.7) !important;
}

/* ----- trace card list (flowchart explorer left column) ----- */
.trace-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 6px 8px;
    margin-bottom: 6px;
}
.trace-card-active {
    border-color: rgba(59,130,246,0.55);
    background: rgba(59,130,246,0.10);
}

/* ----- right metadata panel ----- */
/* ----- right metadata panel ----- */
.meta-wrap {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 14px 14px 10px 14px;
    font-size: 12.5px;
}
.meta-section { margin-bottom: 14px; }
.meta-section h5 {
    margin: 0 0 6px 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
    font-weight: 700;
}
.meta-kv {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 4px 10px;
    font-size: 12px;
}
.meta-kv .k { color: #9ca3af; }
.meta-kv .v { color: #e5e7eb; font-family: ui-monospace, monospace; word-break: break-all; }
/* KV row emphasis (used for Token counts in the right panel).
   On Streamlit light theme the default `.v` color (#e5e7eb) is almost
   invisible against the white card. This modifier deepens the value
   text and gives it tabular numeric + bold weight. */
.meta-kv.strong .k { color: #4b5563; font-weight: 600; }
.meta-kv.strong .v {
    color: #111827;                     /* gray-900, near-black */
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    font-size: 13.5px;
}
.meta-pill {
    display: inline-block; padding: 1px 8px; border-radius: 999px;
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase;
}
.meta-pill.ok    { background: rgba(16,185,129,0.18); color: #a7f3d0; }
.meta-pill.err   { background: rgba(239,68,68,0.18);  color: #fecaca; }
.meta-pill.run   { background: rgba(245,158,11,0.18); color: #fde68a; }
.meta-pill.unset { background: rgba(107,114,128,0.18); color: #d1d5db; }

/* ----- detail panel ----- */
.detail-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.detail-card .detail-head {
    display: flex; align-items: center; gap: 8px;
    font-size: 14px; font-weight: 600; color: #f3f4f6;
}
.detail-card .detail-sub {
    color: #9ca3af; font-size: 11.5px; margin-top: 2px;
}
.detail-kv {
    display: grid; grid-template-columns: 130px 1fr;
    gap: 4px 12px; font-size: 12.5px;
}
.detail-kv .k { color: #9ca3af; }
.detail-kv .v {
    color: #e5e7eb; word-break: break-all;
    font-family: ui-monospace, monospace; font-size: 12px;
}
.io-block {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    margin-bottom: 10px;
    overflow: hidden;
}
.io-block-head {
    padding: 8px 12px;
    background: rgba(255,255,255,0.04);
    font-size: 12px; font-weight: 600; color: #e5e7eb;
    display: flex; align-items: center; gap: 8px;
}
.io-block-head .io-arrow { color: #9ca3af; font-size: 11px; }
.io-block-body {
    padding: 10px 12px;
    max-height: 480px;
    overflow-y: auto;
    background: rgba(0,0,0,0.18);
}
.callout-err {
    background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.3);
    border-radius: 8px; padding: 12px; color: #fecaca;
    font-family: ui-monospace, monospace; font-size: 12px; white-space: pre-wrap;
}
.kind-pill {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    color: #fff; font-size: 10.5px; font-weight: 700;
    letter-spacing: 0.04em; text-transform: uppercase;
}
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { padding: 6px 10px; font-size: 12.5px; }
.stExpander details summary { font-size: 12.5px; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.22); }
::-webkit-scrollbar-track { background: transparent; }

/* ----- Message card (Run tab Input/Output) ----- */
/* Each LLM message is rendered as a role-chipped card with a 4-line
   vertically scrollable body. Replaces st.chat_message which forced a
   single-line bubble and horizontally scrolled long unbreakable tokens. */
.msg-card {
    margin: 6px 0 10px 0;
    background: rgba(255,255,255,0.035);
    border-radius: 6px;
    overflow: hidden;
}
.msg-card .msg-head {
    padding: 4px 10px;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    background: rgba(0,0,0,0.18);
    display: flex;
    align-items: center;
    gap: 6px;
}
.msg-card .msg-role-label { font-weight: 700; }
.msg-card .msg-body {
    max-height: 18em;
    overflow-y: auto;
    overflow-wrap: anywhere;
    word-break: break-word;
    padding: 6px 10px 8px 10px;
    margin: 0;
    font-size: 12.5px;
    line-height: 1.45;
    color: #d1d5db;
}
.msg-card .msg-meta {
    padding: 3px 10px;
    font-size: 10.5px;
    color: #9ca3af;
    background: rgba(255,255,255,0.02);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.msg-card .msg-part-block {
    margin: 6px 0;
    padding: 6px 8px;
    border-left: 2px solid rgba(59,130,246,0.5);
    background: rgba(59,130,246,0.06);
    border-radius: 0 4px 4px 0;
    font-size: 11.5px;
}
.mermaid .nodeLabel, .mermaid .node rect, .mermaid .node polygon {
    cursor: pointer;
}
    overflow-y: auto;
    overflow-wrap: anywhere;
    word-break: break-word;
    padding: 6px 10px 8px 10px;
    margin: 0;
    font-size: 12.5px;
    line-height: 1.45;
    color: #d1d5db;
}
.msg-card .msg-body > p:first-child { margin-top: 0; }
.msg-card .msg-body > p:last-child  { margin-bottom: 0; }
.msg-card .msg-body pre {
    margin: 4px 0;
    padding: 6px 8px;
    background: rgba(0,0,0,0.25);
    border-radius: 4px;
    font-size: 11.5px;
    white-space: pre-wrap;
    word-break: break-all;
}
.msg-card .msg-body::-webkit-scrollbar { width: 6px; }
.msg-card .msg-body::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.18);
        border-radius: 3px;
    }
    .msg-card .msg-body::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.28);
    }
    .msg-card .msg-body::-webkit-scrollbar-track { background: transparent; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Cost estimation - rough USD per 1k tokens for known providers/models
# ---------------------------------------------------------------------------
_COST_PER_1K = {
    # OpenAI
    ("openai", "gpt-4o"):        (0.0025, 0.0100),
    ("openai", "gpt-4o-mini"):   (0.00015, 0.0006),
    ("openai", "gpt-4-turbo"):   (0.010, 0.030),
    ("openai", "gpt-4"):         (0.030, 0.060),
    ("openai", "gpt-3.5-turbo"): (0.0005, 0.0015),
    ("openai", "o1"):            (0.015, 0.060),
    ("openai", "o1-mini"):       (0.003, 0.012),
    # Anthropic
    ("anthropic", "claude-3-5-sonnet"):  (0.003, 0.015),
    ("anthropic", "claude-3-opus"):      (0.015, 0.075),
    ("anthropic", "claude-3-haiku"):     (0.00025, 0.00125),
}


def _estimate_cost(span: dict, attr_key: str) -> float | None:
    """Return USD estimate for an LLM span, or None if unknown."""
    attrs = span.get("attributes") or {}
    model = canon(attrs, "model") or ""
    provider = (canon(attrs, "model.provider") or "").lower()
    model_l = model.lower()
    # Match by provider + model
    rates = _COST_PER_1K.get((provider, model_l))
    if rates is None:
        # Try by model only (skip provider)
        for (p, m), r in _COST_PER_1K.items():
            if m == model_l:
                rates = r
                break
    if rates is None:
        return None
    tin = canon(attrs, attr_key + ".tokens.input") or canon(attrs, "tokens.input")
    tout = canon(attrs, attr_key + ".tokens.output") or canon(attrs, "tokens.output")
    if not isinstance(tin, int) and not isinstance(tout, int):
        return None
    cost_in = (tin or 0) / 1000.0 * rates[0]
    cost_out = (tout or 0) / 1000.0 * rates[1]
    return round(cost_in + cost_out, 4)


# ---------------------------------------------------------------------------
# Trace KPI dataclass + aggregator
# ---------------------------------------------------------------------------
@dataclass
class TraceKPI:
    n_spans: int = 0
    n_errors: int = 0
    n_llm: int = 0
    n_tool: int = 0
    n_chain: int = 0
    n_agent: int = 0
    n_prompt: int = 0
    t_in: int = 0
    t_out: int = 0
    tok_present: bool = False
    dur_ms: float = 0.0
    start_ns: int = 0
    end_ns: int = 0
    final_status: str = "UNSET"
    service_name: str = ""
    agent_names: list = field(default_factory=list)
    cost_usd: float = 0.0


def _aggregate_kpi(spans: list) -> TraceKPI:
    k = TraceKPI()
    k.n_spans = len(spans)
    if not spans:
        return k
    starts = [int(s.get("start_time", 0)) for s in spans]
    ends = [int(s.get("end_time", 0)) for s in spans]
    k.start_ns = min(starts)
    k.end_ns = max(ends)
    k.dur_ms = (k.end_ns - k.start_ns) / 1_000_000
    services: list = []
    for s in spans:
        attrs = s.get("attributes") or {}
        kind = span_kind(attrs)
        st_ = str(s.get("status", "")).upper()
        if st_ == "ERROR":
            k.n_errors += 1
        if kind == "LLM":
            k.n_llm += 1
            tin = canon(attrs, "tokens.input")
            tout = canon(attrs, "tokens.output")
            if isinstance(tin, int):
                k.t_in += tin; k.tok_present = True
            if isinstance(tout, int):
                k.t_out += tout; k.tok_present = True
            cost = _estimate_cost(s, "tokens")
            if cost is not None:
                k.cost_usd += cost
        elif kind == "TOOL":
            k.n_tool += 1
        elif kind == "CHAIN":
            k.n_chain += 1
        elif kind == "AGENT":
            k.n_agent += 1
        elif kind == "PROMPT":
            k.n_prompt += 1
        sn = s.get("service_name")
        if isinstance(sn, str) and sn:
            services.append(sn)
    if services:
        k.service_name = Counter(services).most_common(1)[0][0]
    for s in spans:
        if span_kind(s.get("attributes") or {}) == "AGENT":
            nm = s.get("name")
            if nm and nm not in k.agent_names:
                k.agent_names.append(nm)
    if not k.agent_names and spans:
        roots = [s for s in spans if not s.get("parent_span_id")]
        if roots:
            rname = roots[0].get("name") or ""
            if rname:
                k.agent_names = [rname]
    statuses = {str(s.get("status", "")).upper() for s in spans}
    if "ERROR" in statuses:
        k.final_status = "ERROR"
    elif "OK" in statuses:
        k.final_status = "OK"
    else:
        k.final_status = "UNSET"
    return k


# ---------------------------------------------------------------------------
# JSONL loader + auto-discovery of trace files
# ---------------------------------------------------------------------------
# Candidate paths in priority order. The first existing one wins by default.
_DEFAULT_TRACE_PATHS = [
    Path(os.environ.get("TRACE_FILE", "")),
    Path("latest_traces.jsonl"),
    Path("D:/agent/complex-agent-langchain/latest_traces.jsonl"),
    Path("D:/my-projects/agent-monitor/latest_traces.jsonl"),
]


def _discover_trace_sources() -> list:
    """Return [(display_label, Path), ...] sorted by mtime desc."""
    seen = set()
    out = []
    for p in _DEFAULT_TRACE_PATHS:
        try:
            p = Path(p)
        except Exception:
            continue
        if not p or str(p) in seen:
            continue
        seen.add(str(p))
        if p.is_file():
            try:
                mtime = p.stat().st_mtime
                size = p.stat().st_size
            except OSError:
                continue
            _mtime_str = _time.strftime("%H:%M:%S", _time.localtime(mtime))
            label = f"{p}  ·  {size // 1024} KB  ·  {_mtime_str}"
            out.append((label, p))
    out.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
    return out


@st.cache_data(show_spinner=False, ttl=2)
def load_traces(path_str: str) -> tuple:
    traces: dict = defaultdict(list)
    dropped = 0
    p = Path(path_str)
    if not p.is_file():
        return dict(traces), dropped
    with p.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                dropped += 1
                continue
            if _migrate_record is not None:
                try:
                    span = _migrate_record(span)
                except Exception:
                    pass
            tid = span.get("trace_id")
            if not tid:
                dropped += 1
                continue
            traces[tid].append(span)
    return dict(traces), dropped


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------
def _extract_error_info(span: dict) -> dict:
    out = {"status_message": "", "exception_type": "", "stack": ""}
    attrs = span.get("attributes") or {}
    status = span.get("status")
    if isinstance(status, dict):
        out["status_message"] = status.get("message") or ""
    for evt in span.get("events") or []:
        if not isinstance(evt, dict):
            continue
        if evt.get("name") == "exception":
            eattrs = evt.get("attributes") or {}
            out["exception_type"] = (
                eattrs.get("exception.type") or eattrs.get("exception_type") or ""
            )
            out["stack"] = (
                eattrs.get("exception.stacktrace")
                or eattrs.get("exception.stack_trace")
                or eattrs.get("stack_trace")
                or ""
            )
            if not out["status_message"]:
                out["status_message"] = (
                    eattrs.get("exception.message")
                    or eattrs.get("exception_message")
                    or ""
                )
    if not out["status_message"]:
        out["status_message"] = attrs.get("error.message") or attrs.get("exception.message") or ""
    if not out["stack"]:
        out["stack"] = attrs.get("error.stack") or attrs.get("exception.stacktrace") or ""
    if not out["exception_type"]:
        out["exception_type"] = attrs.get("error.type") or attrs.get("exception.type") or ""
    return out


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
st.session_state.setdefault("trace_source", None)
st.session_state.setdefault("selected_trace", None)
st.session_state.setdefault("selected_span", None)


# ---------------------------------------------------------------------------
# Trace source picker + loader
# ---------------------------------------------------------------------------
sources = _discover_trace_sources()
_dbg(f"discovered {len(sources)} source(s)")
for _lbl, _p in sources:
    _dbg(f"  source: {_p}  ({_p.stat().st_size // 1024} KB)")

if not sources:
    st.markdown(
        """
        <div style="padding: 60px 20px; text-align: center; color: #9ca3af;">
            <div style="font-size: 48px;">🔎</div>
            <h2 style="margin-top: 8px; color: #e5e7eb;">No trace files found</h2>
            <p>The viewer looked in:</p>
            <ul style="display: inline-block; text-align: left;">
                <li><code>$TRACE_FILE</code> env var</li>
                <li><code>./latest_traces.jsonl</code> (cwd)</li>
                <li><code>D:/agent/complex-agent-langchain/latest_traces.jsonl</code></li>
                <li><code>D:/my-projects/agent-monitor/latest_traces.jsonl</code></li>
            </ul>
            <p>Start your agent with
              <code style="background: rgba(255,255,255,0.06); padding: 4px 8px; border-radius: 4px;">
                monitor(..., exporter="jsonl")
              </code>
            and refresh.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()



# Pick the most-recently-modified file by default
if st.session_state.trace_source is None or str(st.session_state.trace_source) not in [str(p) for _, p in sources]:
    st.session_state.trace_source = str(sources[0][1])

active_label, active_path = next(
    ((lbl, p) for lbl, p in sources if str(p) == st.session_state.trace_source),
    sources[0],
)
traces, dropped = load_traces(str(active_path))
_dbg(f"loaded {len(traces)} trace(s), {sum(len(s) for s in traces.values())} span(s), {dropped} dropped from {active_path}")


def _latest_start(tid: str) -> int:
    return max((int(s.get("start_time", 0)) for s in traces.get(tid, [])), default=0)


_sort_key = lambda t: (len(traces[t]), _latest_start(t))
trace_ids = sorted(traces.keys(), key=_sort_key, reverse=True)
_dbg(f"BEFORE: {len(trace_ids)} trace id(s); selected_trace = {st.session_state.selected_trace!r}; in traces = {st.session_state.selected_trace in traces}")
# Always ensure a valid selection
if not trace_ids:
    _dbg("ABORT: no trace_ids loaded")
elif st.session_state.selected_trace is None or st.session_state.selected_trace not in traces:
    _old = st.session_state.selected_trace
    st.session_state.selected_trace = trace_ids[0]
    st.session_state.selected_span = None
    _dbg(f"FIX: selected_trace was {_old!r}, now SET to {st.session_state.selected_trace!r}")
else:
    _dbg(f"KEEP: selected_trace = {st.session_state.selected_trace!r} (valid)")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
hdr_l, hdr_m, hdr_r = st.columns([2, 3, 2])
with hdr_l:
    st.markdown("## 🔎 Agent 链路监控  `v3-3col`", unsafe_allow_html=True)
    st.caption(
        f"**{len(traces)}** traces / **{sum(len(s) for s in traces.values())}** spans"
        + (f"  ·  _dropped {dropped} malformed rows_" if dropped else "")
    )
with hdr_m:
    if len(sources) > 1:
        try:
            cur_idx = [str(p) for _, p in sources].index(str(active_path))
        except ValueError:
            cur_idx = 0
        new_path_str = st.selectbox(
            "数据源",
            options=[str(p) for _, p in sources],
            index=cur_idx,
            format_func=lambda s: next(lbl for lbl, p in sources if str(p) == s),
            label_visibility="collapsed",
        )
        if new_path_str != str(active_path):
            st.session_state.trace_source = new_path_str
            st.session_state.selected_trace = None
            st.session_state.selected_span = None
            for _k in ('focus', 'trace'):
                if _k in st.query_params:
                    del st.query_params[_k]
            st.rerun()
    else:
        pass  # single-source mode: do not render the raw path caption
with hdr_r:
    if trace_ids:
        try:
            idx = trace_ids.index(st.session_state.selected_trace)
        except ValueError:
            idx = 0

# Generic suffixes that mean "this is just infra, not the purpose".
        # Used to strip the trailing noise from names like
        # "verify_claim_executor" -> "Verify Claim".
        _PURPOSE_SUFFIX_DROP = {
            "executor", "run", "invoke", "call", "step", "agent", "handler",
            "service", "workflow", "pipeline", "chain", "sequence", "task",
            "node", "func", "function", "method", "process", "runner",
            "controller", "manager", "orchestrator", "wrapper", "adapter",
        }

        def _short_purpose(name: str) -> str:
            """Convert an arbitrary span name into a 1-4 word Purpose phrase.

            Examples::

                verify_claim_executor  -> "Verify Claim"
                persist_report         -> "Persist Report"
                RecheckNews            -> "Recheck News"
                decompose_claim        -> "Decompose Claim"
                _web_search            -> "Web Search"

            Snake_case is split on underscores; PascalCase / camelCase on
            capital letters. Common "infra" suffixes (_executor, _run,
            _agent, _chain, ...) are stripped. Result is capped at 4 words.
            """
            if not isinstance(name, str):
                return ""
            s = name.strip().lstrip("_")
            if not s:
                return ""
            if "_" in s or "-" in s:
                parts = re.split(r"[_-]+", s)
            else:
                # split PascalCase / camelCase: capital letter is a boundary
                parts = re.split(r"(?=[A-Z])", s)
                parts = [p for p in parts if p]
            # drop trailing generic suffixes
            while parts and parts[-1].lower() in _PURPOSE_SUFFIX_DROP:
                parts.pop()
            if not parts:
                # all words were suffixes -> keep the raw cleaned name
                return " ".join(w.capitalize() for w in re.split(r"[_-]+", s))[:40]
            pretty = [w.capitalize() if w.islower() else w for w in parts]
            if len(pretty) > 4:
                pretty = pretty[:4]
            return " ".join(pretty)

        def _trace_label(spans: list) -> str:
            """Derive a 2-4 word purpose label for the dropdown.

            Goal: the dropdown row should answer "what does this trace DO?"
            without the user having to click into it. We deliberately avoid
            dumping user input content here (it bloats rows; content varies
            across iterations of the same agent).

            Resolution:
              1. If the root name is a meaningful business name (not a
                 generic LangChain wrapper), shorten it via _short_purpose.
              2. Pattern-match LangChain internals:
                 - RunnableParallel<tools...>  -> "多任务并行（n）"
                 - RunnableSequence with TOOL child spans -> "工具型智能体"
                 - RunnableSequence with RETRIEVER child spans -> "检索链"
                 - RunnableSequence (Prompt -> LLM -> Parser) -> "LLM 调用链"
                 - RunnableSequence (just LLM) -> "大模型调用"
              3. Friendly name via viewer.naming on the root name.
              4. Last resort: "(unnamed)".
            """
            if not spans:
                return "(empty trace)"
            root = next(
                (s for s in spans if not s.get("parent_span_id")),
                spans[0],
            )
            root_id = root.get("span_id")
            root_name = root.get("name") or ""
            root_kind = (root.get("kind") or "").upper()
            children = [
                s for s in spans
                if s.get("parent_span_id") == root_id
            ]
            child_kinds = {c.get("kind", "").upper() for c in children}
            child_names = {c.get("name", "") for c in children}

            # ---- 1) Real business name on root? ----
            if root_name and not root_name.startswith("Runnable"):
                p = _short_purpose(root_name)
                if p:
                    return p

            # ---- 2) LangChain wrapper patterns ----
            if root_name.startswith("RunnableParallel"):
                m = re.match(r"^RunnableParallel<(.+)>$", root_name)
                if m:
                    tools = [t.strip() for t in m.group(1).split(",") if t.strip()]
                    n = len(tools)
                    if n == 0:
                        return "Parallel Branches"
                    if n == 1:
                        return f"Parallel: {_short_purpose(tools[0]) or tools[0]}"
                    if n == 2:
                        a = _short_purpose(tools[0]) or tools[0]
                        b = _short_purpose(tools[1]) or tools[1]
                        return f"Parallel: {a} + {b}"
                    return f"Parallel Search ({n})"
                return "Parallel Branches"

            if root_name.startswith("RunnableSequence"):
                # LangChain instruments ChatPromptTemplate, OutputParser,
                # StrOutputParser, etc. all as kind=CHAIN. So we must
                # detect Prompt/Parser/LLM by NAME patterns - not just by
                # span_kind - otherwise everything classifies as "LLM Call".
                child_names_l = list(child_names)
                child_names_lc = [n.lower() for n in child_names_l]

                has_tool = (
                    "TOOL" in child_kinds
                    or any(n.endswith("Tool") or "tool" in n.lower() for n in child_names_l)
                )
                has_retriever = (
                    "RETRIEVER" in child_kinds
                    or any("retriever" in n.lower() for n in child_names_lc)
                )
                has_parser = any(
                    n.endswith("OutputParser") or n.endswith("Parser")
                    or "OutputParser" in n for n in child_names_l
                )
                has_prompt = any(
                    n.endswith("PromptTemplate") or n.endswith("Prompt")
                    or "PromptTemplate" in n for n in child_names_l
                )
                has_llm = (
                    "LLM" in child_kinds
                    or any(n.startswith("Chat") and "Prompt" not in n for n in child_names_l)
                )

                if has_tool:
                    return "Tool Agent"
                if has_retriever:
                    return "Retrieval Chain"
                if has_llm:
                    if has_prompt and has_parser:
                        return "LLM Chain"
                    if has_prompt:
                        return "LLM Call (templated)"
                    return "LLM Call"
                # No LLM detected - try to surface a meaningful child name
                for c in children:
                    cn = c.get("name") or ""
                    if cn and not cn.startswith("Runnable") and not cn.startswith("_"):
                        p = _short_purpose(cn)
                        if p:
                            return p
                return "Chain Step"

            # ---- 3) friendly_name fallthrough ----
            try:
                from viewer.naming import friendly_name as _fn
                display, _ = _fn(root_name, root_kind)
                if display and display != root_name:
                    short = _short_purpose(display) or display
                    if short:
                        return short[:40]
            except Exception:
                pass

            # ---- 4) raw name shortener ----
            p = _short_purpose(root_name)
            if p:
                return p[:40]
            return "(unnamed)"

        def _fmt_trace_option(t: str) -> str:
            """Self-explaining dropdown label.

            Layout:  <status_icon> <label>  <spans>sp <duration>  <tid8>

            The status icon is the first column so users can scan ERROR
            traces from a long list in one glance. The label gives the
            trace's purpose (user input or root span name). The trace_id
            suffix is the disambiguator when many traces share a label.
            """
            spans = traces[t] or []
            kk = _aggregate_kpi(spans)
            label = _trace_label(spans)
            if kk.final_status == "ERROR":
                ico = "❌"  # 红色叉（错误）
            elif kk.final_status == "OK":
                ico = "✅"  # 绿色勾（成功）
            else:
                ico = "⏳"  # 沙漏（未完成）
            return (
                f"{ico}  {label}  "
                f"·  {kk.n_spans} spans  "
                f"·  {_format_duration_ms(kk.dur_ms)}  "
                f"·  {t[:8]}"
            )

        new_tid = st.selectbox(
            "Trace",
            options=trace_ids,
            index=idx,
            format_func=_fmt_trace_option,
            label_visibility="collapsed",
        )
        if new_tid != st.session_state.selected_trace:
            st.session_state.selected_trace = new_tid
            st.session_state.selected_span = None
            # drop stale URL-carried navigation params when switching traces
            for _k in ('focus', 'trace'):
                if _k in st.query_params:
                    del st.query_params[_k]
            st.rerun()




# ---------------------------------------------------------------------------
# Build filtered span list + tree structure
# ---------------------------------------------------------------------------
sel_tid = st.session_state.selected_trace
sel_spans = traces[sel_tid] if sel_tid else []
kpi = _aggregate_kpi(sel_spans)


all_by_id = {s["span_id"]: s for s in sel_spans}
filtered_spans = list(sel_spans)

# Parent/child map (over filtered spans)
spans_sorted = sorted(filtered_spans, key=lambda s: int(s.get("start_time", 0)))
by_id = {s["span_id"]: s for s in spans_sorted}
children_map: dict = defaultdict(list)
roots: list = []
for s in spans_sorted:
    pid = s.get("parent_span_id")
    if pid and pid in by_id:
        children_map[pid].append(s)
    else:
        roots.append(s)
for c in children_map.values():
    c.sort(key=lambda s: int(s.get("start_time", 0)))


# ---------------------------------------------------------------------------
# Flowchart mode (Mermaid) + click-to-zoom
# ---------------------------------------------------------------------------
_MERMAID_MAX_NODES = 80
_NODE_LABEL_MAX_CHARS = 60


def _mermaid_safe_id(sid):
    return 'n_' + sid.replace('-', '_')


def _mermaid_label(span):
    attrs = span.get('attributes') or {}
    kind = span_kind(attrs)
    info = SPAN_KINDS.get(kind, SPAN_KINDS['UNKNOWN'])
    icon = info[0]
    name = _span_display_name(span)
    name = re.sub(r'[\"\\#;|]', ' ', name).strip()
    if len(name) > _NODE_LABEL_MAX_CHARS:
        name = name[:_NODE_LABEL_MAX_CHARS - 1] + '...'
    start_ns = int(span.get('start_time', 0))
    end_ns = int(span.get('end_time', 0))
    dur_ms = (end_ns - start_ns) / 1_000_000
    dur = _format_duration_ms(dur_ms)
    return f'<b>{icon} {name}</b><br/><small>{kind} &middot; {dur}</small>'


def _build_mermaid(spans, *, focus=None, hops=2):
    if not spans:
        return 'flowchart TD\n    empty[　（无 span）　]'
    spans_by_id = {s['span_id']: s for s in spans}
    if focus and focus in spans_by_id:
        visible = {focus}
        up, down = {focus}, {focus}
        for _ in range(hops):
            new_up = set()
            for sid in up:
                pid = spans_by_id.get(sid, {}).get('parent_span_id')
                if pid and pid in spans_by_id and pid not in visible:
                    new_up.add(pid)
            visible |= new_up
            up = new_up
            new_down = set()
            for sid in down:
                for s in spans:
                    if s.get('parent_span_id') == sid and s['span_id'] not in visible:
                        new_down.add(s['span_id'])
            visible |= new_down
            down = new_down
    else:
        visible = {s['span_id'] for s in spans}
    visible_spans = [s for s in spans if s['span_id'] in visible]
    if len(visible_spans) > _MERMAID_MAX_NODES and not focus:
        return (
            'flowchart TD\n'
            '    root[<　共 ' + str(len(spans)) + ' 个 span　<br/>'
            '<small>节点数过多，请切回 列表 模式查看</small>]\n'
            '    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\n'
            '    class root root;')
    visible_spans.sort(key=lambda s: int(s.get('start_time', 0)))
    starts = [int(s.get('start_time', 0)) for s in visible_spans]
    min_start = min(starts) if starts else 0
    out = ['flowchart TD']
    for css in [
        '    classDef llm       fill:#1d4ed8,color:#fff,stroke:#1e3a8a,stroke-width:1px;',
        '    classDef chain     fill:#065f46,color:#fff,stroke:#064e3b,stroke-width:1px;',
        '    classDef tool      fill:#b45309,color:#fff,stroke:#7c2d12,stroke-width:1px;',
        '    classDef agent     fill:#a16207,color:#fff,stroke:#713f12,stroke-width:1px;',
        '    classDef retriever fill:#7e22ce,color:#fff,stroke:#581c87,stroke-width:1px;',
        '    classDef embedding fill:#0e7490,color:#fff,stroke:#164e63,stroke-width:1px;',
        '    classDef reranker  fill:#6d28d9,color:#fff,stroke:#4c1d95,stroke-width:1px;',
        '    classDef prompt    fill:#3f6212,color:#fff,stroke:#365314,stroke-width:1px;',
        '    classDef parser    fill:#4b5563,color:#fff,stroke:#1f2937,stroke-width:1px;',
        '    classDef evaluator fill:#a8a29e,color:#1c1917,stroke:#78716c,stroke-width:1px;',
        '    classDef guardrail fill:#b91c1c,color:#fff,stroke:#7f1d1d,stroke-width:1px;',
        '    classDef unknown   fill:#6b7280,color:#fff,stroke:#374151,stroke-width:1px;',
        '    classDef error     stroke:#ef4444,stroke-width:2px,color:#fff;',
        '    classDef focus     stroke:#facc15,stroke-width:3px;',
        '    linkStyle default stroke:#64748b,stroke-width:1px;']:
        out.append(css)
    children_by_parent = {}
    for s in visible_spans:
        pid = s.get('parent_span_id')
        if pid and pid in visible:
            children_by_parent.setdefault(pid, []).append(s)
    _handled_parents = set()
    for span in visible_spans:
        sid = span['span_id']
        nid = _mermaid_safe_id(sid)
        kind = span_kind(span.get('attributes') or {})
        kind_class = kind.lower() if kind in SPAN_KINDS else 'unknown'
        cls = [kind_class]
        if str(span.get('status', '')).upper() == 'ERROR':
            cls.append('error')
        if sid == focus:
            cls.append('focus')
        start_ns = int(span.get('start_time', 0))
        offset_ms = int((start_ns - min_start) / 1_000_000)
        label = _mermaid_label(span)
        full_label = f"{label}<br/><small>t+{offset_ms}ms</small>"
        safe = re.sub(r'[\"\\#;|]', ' ', full_label).strip()
        out.append(f'    {nid}["{safe}"]')
        out.append(f'    class {nid} {",".join(cls)};')
    for parent_id, kids in children_by_parent.items():
        if len(kids) < 2:
            continue
        sorted_kids = sorted(kids, key=lambda s: int(s.get('start_time', 0)))
        n_kids = len(sorted_kids)
        all_sequential = True
        for i in range(n_kids - 1):
            prev_end = int(sorted_kids[i].get('end_time', 0))
            next_start = int(sorted_kids[i + 1].get('start_time', 0))
            if next_start < prev_end:
                all_sequential = False
                break
        pnid = _mermaid_safe_id(parent_id)
        if all_sequential:
            _handled_parents.add(parent_id)
            first_id = _mermaid_safe_id(sorted_kids[0]['span_id'])
            out.append(f'    {pnid} --> {first_id}')
            for i in range(n_kids - 1):
                a = _mermaid_safe_id(sorted_kids[i]['span_id'])
                b = _mermaid_safe_id(sorted_kids[i + 1]['span_id'])
                out.append(f'    {a} --> {b}')
        else:
            _handled_parents.add(parent_id)
            out.append('    subgraph SG_' + pnid + '["并行分支"]')
            out.append('    direction LR')
            for k in sorted_kids:
                out.append('        ' + _mermaid_safe_id(k['span_id']))
            out.append('    end')
            for k in sorted_kids:
                out.append(f'    {pnid} --> {_mermaid_safe_id(k["span_id"])}')
    for span in visible_spans:
        pid = span.get('parent_span_id')
        if pid and pid in visible and pid not in _handled_parents:
            out.append(f'    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span["span_id"])}')
    return '\n'.join(out)


def _render_flowchart_component(sel_spans, *, focus=None, trace_id=''):
    """Render the mermaid flowchart inside a bidirectional component.

    Clicking a span node makes the frontend send the span_id back via the
    component protocol -> Streamlit reruns in-place (NO full-page reload) ->
    ``st.session_state.selected_span`` is updated -> the right-hand detail
    column switches to that span.  The URL is only synced for deep-linking;
    it is never used to navigate the page.
    """
    if _flowchart_component is None:
        st.warning('未找到 flowchart_component/，无法渲染流程图。')
        return
    sel_ids = {s['span_id'] for s in sel_spans}
    # Always render the FULL flowchart (no click-to-zoom).  Clicking a node
    # only highlights it and switches the right-hand detail; the middle column
    # keeps showing every span node as the user expects.
    mermaid_src = _build_mermaid(sel_spans, focus=None)
    clicked = _flowchart_component(
        mermaid_src=mermaid_src,
        focus=focus or '',
        trace_id=trace_id or '',
        default=None,
        key=f'flowchart_{trace_id or "default"}',
    )
    if isinstance(clicked, dict) and clicked.get('span_id'):
        # The component keeps the last sent value across reruns.  Deduplicate
        # with the per-click timestamp so a *stale* value never re-selects a
        # span (e.g. right after "back to overview"), while a *new* click on
        # the same span still works.
        ts = clicked.get('ts')
        if ts is not None and ts != st.session_state.get('_last_flow_click_ts'):
            st.session_state._last_flow_click_ts = ts
            sid = str(clicked['span_id'])
            if sid in sel_ids:
                st.session_state.selected_span = sid
                # Sync URL for deep-linking only — st.query_params updates go
                # through the frontend history API and do NOT reload the page.
                if st.query_params.get('focus') != sid:
                    st.query_params['focus'] = sid
                if trace_id and st.query_params.get('trace') != trace_id:
                    st.query_params['trace'] = trace_id


def _render_flowchart_mode(sel_spans, kpi, all_by_id):
    # Restore the trace from the URL after a page reload / deep link.  The URL
    # is only READ here (never navigated to), so this cannot cause the
    # "click -> page jumps" behaviour.
    _url_trace = st.query_params.get('trace')
    if _url_trace and _url_trace in traces:
        if st.session_state.selected_trace != _url_trace:
            st.session_state.selected_trace = _url_trace
            sel_spans = traces[_url_trace]
            all_by_id = {s['span_id']: s for s in sel_spans}
            kpi = _aggregate_kpi(sel_spans)
    # Deep-link focus: apply ?focus= exactly once per session (right after a
    # page reload).  Afterwards, st.session_state.selected_span is the single
    # source of truth; "back to overview" must not be undone by a stale URL.
    if not st.session_state.get('_url_focus_applied'):
        f = st.query_params.get('focus')
        if f and f in all_by_id:
            st.session_state.selected_span = f
        st.session_state._url_focus_applied = True
    cur_sel = st.session_state.selected_span
    if cur_sel and cur_sel not in all_by_id:
        st.session_state.selected_span = None
        cur_sel = None
    col_left, col_center, col_right = st.columns([1.1, 1.8, 2.6])  # trace list / flowchart / span detail; right panel fixed at 2.60
    with col_left:
        _render_trace_cards_list()
    with col_center:
        _render_flowchart_center(
            sel_spans,
            focus=cur_sel or None,
            trace_id=st.session_state.selected_trace,
        )
    with col_right:
        _render_detail_column(sel_spans, all_by_id)


def _render_trace_cards_list():
    st.markdown('#### 📋 Traces')
    if not traces:
        st.caption('还没有 trace。请运行 agent 后刷新。')
        return
    cur_tid = st.session_state.selected_trace
    sorted_tids = sorted(traces.keys(), key=_trace_start_ns)
    for tid in sorted_tids:
        row = _fmt_trace_option(tid)
        is_cur = (tid == cur_tid)
        btn_type = 'primary' if is_cur else 'secondary'
        active_cls = ' trace-card-active' if is_cur else ''
        st.markdown(f'<div class="trace-card{active_cls}">', unsafe_allow_html=True)
        st.button(
            row,
            key=f'trace_card_{tid}',
            type=btn_type,
            use_container_width=True,
            on_click=_select_trace,
            args=(tid,),
        )
        st.markdown('</div>', unsafe_allow_html=True)


def _render_flowchart_center(sel_spans, *, focus=None, trace_id=''):
    """Render the Mermaid flowchart. Pass focus=<span_id> to highlight the matching node (yellow border via the focus classDef)."""
    st.markdown('#### 🔀 Agent 流程图')
    st.caption(
        f'共 {len(sel_spans)} 个 span。'
        '点击节点查看详情；'
        '上方为起始时间最早的节点。'
    )
    _render_flowchart_component(sel_spans, focus=focus, trace_id=trace_id)


def _render_detail_column(sel_spans, all_by_id):
    """Render the span-detail column. ``st.session_state.selected_span`` is the
    single source of truth (updated by flowchart node clicks, no page reload)."""
    st.markdown('#### 🔍 Span 详情')

    sel = st.session_state.selected_span
    roots = [s for s in sel_spans if not s.get('parent_span_id')]
    root_id = roots[0]['span_id'] if roots else None
    if sel and sel in all_by_id:
        if sel != root_id:
            if st.button('← 返回全貌', key='back_to_overview'):
                _clear_focus()
    else:
        if root_id:
            st.session_state.selected_span = root_id

    _render_detail_panel(sel_spans, by_id_all=all_by_id)


def _jump_to_span(span_id):
    st.session_state.selected_span = span_id
    if st.query_params.get('focus') != span_id:
        st.query_params['focus'] = span_id
    st.rerun()


def _clear_focus():
    st.session_state.selected_span = None
    if 'focus' in st.query_params:
        del st.query_params['focus']
    st.rerun()


def _select_trace(tid):
    st.session_state.selected_trace = tid
    # Clear URL-carried navigation params so a later node click re-sets them
    # for the newly selected trace (otherwise a stale ?trace= would force the
    # app back to the previous trace after the reload).
    for _k in ('focus', 'trace'):
        if _k in st.query_params:
            del st.query_params[_k]


def _trace_start_ns(tid):
    spans = traces.get(tid) or []
    if not spans:
        return 0
    return min(int(s.get('start_time', 0)) for s in spans)

def _render_detail_panel(all_spans: list, *, by_id_all: dict) -> None:
    sel_sid = st.session_state.selected_span
    sel_span = by_id_all.get(sel_sid) if sel_sid else None

    if not sel_span:
        st.markdown(
            '<div class="detail-card" style="text-align:center;color:#9ca3af;'
            'padding:36px 16px;">'
            '<div style="font-size:34px;">👈</div>'
            '<div style="margin-top:6px;">请在左侧树中选中一个节点查看详情。</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    attrs = sel_span.get("attributes") or {}
    kind = span_kind(attrs)
    disp = _span_display_name(sel_span)
    status = str(sel_span.get("status", "")).upper()
    start_ns = int(sel_span.get("start_time", 0))
    end_ns = int(sel_span.get("end_time", 0))
    dur_ms = (end_ns - start_ns) / 1_000_000
    err = _extract_error_info(sel_span) if status == "ERROR" else None
    is_err = bool(err and (err["status_message"] or err["stack"] or err["exception_type"]))

    # Header card
    label, cls = _status_label(status)
    st.markdown(
        f'<div class="detail-card">'
        f'  <div class="detail-head">'
        f'    {_kind_pill_html(kind)}'
        f'    <span>{_esc(disp)}</span>'
        f'    <span style="margin-left:auto">'
        f'      <span class="meta-pill {cls}">{_esc(label)}</span>'
        f'    </span>'
        f'  </div>'
        f'  <div class="detail-sub">'
        f'    {_format_duration_ms(dur_ms)}  ·  span_id={_esc(sel_span.get("span_id",""))[:16]}…'
        f'    {("  ·  parent=" + _esc(sel_span.get("parent_span_id") or "(root)")[:16] + "…") if sel_span.get("parent_span_id") else ""}'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["运行", "反馈", "元数据"])

    # ---- Run tab -----------------------------------------------------------
    with tabs[0]:
        _render_run_tab(sel_span, is_err=is_err, err=err)

    # ---- Feedback tab ------------------------------------------------------
    with tabs[1]:
        _render_feedback_tab(sel_span)

    # ---- Metadata tab ------------------------------------------------------
    with tabs[2]:
        _render_metadata_tab(sel_span)


def _render_msg(msg):
    """Render a single LLM message as a structured card."""
    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):
        inner = msg["message"]
        tool_calls = msg.get("tool_calls") or []
    else:
        inner = msg if isinstance(msg, dict) else {"content": msg}
        tool_calls = []
    role = (inner.get("role") or "user").lower()
    content_val = inner.get("content") or ""
    palette = {
        "user":      ("👤", "#10b981", "用户"),
        "human":     ("👤", "#10b981", "用户"),
        "assistant": ("🤖", "#3b82f6", "助手"),
        "ai":        ("🤖", "#3b82f6", "助手"),
        "system":    ("⚙️", "#9ca3af", "系统"),
        "tool":      ("🔧", "#f59e0b", "工具"),
        "function":  ("🔧", "#f59e0b", "工具"),
    }
    key = role or "user"
    icon, color, label = palette.get(key, ("💬", "#6b7280", key.title() if key else "消息"))
    st.markdown(
        f'<div class="msg-card" style="border-left:3px solid {color};">'
        f'<div class="msg-head"><span>{icon}</span>'
        f'<span class="msg-role-label" style="color:{color}">{_esc(label)}</span></div>',
        unsafe_allow_html=True,
    )
    meta_bits = []
    if tool_calls:
        meta_bits.append(f"🔧 {len(tool_calls)} 个工具调用")
    if isinstance(content_val, list):
        meta_bits.append(f"📜 {len(content_val)} 个内容块")
    if meta_bits:
        st.markdown('<div class="msg-meta">' + " &nbsp;·&nbsp; ".join(meta_bits) + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="msg-body">', unsafe_allow_html=True)
    if not content_val:
        st.markdown("<em style='color:#6b7280'>（空）</em>", unsafe_allow_html=True)
    elif isinstance(content_val, str):
        st.markdown(content_val)
    elif isinstance(content_val, list):
        for part in content_val:
            if not isinstance(part, dict):
                st.markdown(_esc(str(part)))
                continue
            ptype = part.get("type")
            if ptype == "text":
                st.markdown(part.get("text", ""))
            elif ptype == "tool_use":
                inp = part.get("input", {})
                if not isinstance(inp, dict):
                    inp = {"value": inp}
                st.markdown(
                    f'<div class="msg-part-block"><b>🔧 工具调用</b>: '
                    f'<code>{_esc(part.get("name", "?"))}</code><br/>'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all">'
                    f'{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}</pre></div>',
                    unsafe_allow_html=True,
                )
            elif ptype == "tool_result":
                res = part.get("content", "")
                st.markdown(
                    f'<div class="msg-part-block"><b>📥 工具结果</b>:'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all">'
                    f'{_esc(str(res)[:600])}</pre></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(_esc(json.dumps(part, ensure_ascii=False)[:600]))
    else:
        st.markdown(_esc(str(content_val)))
    if tool_calls and isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name", "tool")
            args = tc.get("arguments", "")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    pass
            with st.expander(f"🔧 调用 {name}"):
                st.json(args)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("📋 原始 JSON"):
        st.json(msg)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_run_tab(span: dict, *, is_err: bool, err: dict | None) -> None:
    """The primary span view: collapsible Input + Output + Flow state."""
    attrs = span.get("attributes") or {}
    kind = span_kind(attrs)

    # Always-on: ancestor breadcrumb
    # (ancestry shown via parent chip in header)

    # --- Input / Output side-by-side (headers aligned; each side scrolls independently) --
    c_in, c_out = st.columns(2, gap="medium")

    with c_in:
        st.markdown('<div class="io-col-head in-head">⬇  输入</div>', unsafe_allow_html=True)
        if kind == "LLM":
            msgs = to_messages(canon(attrs, "messages.input"))
            if msgs:
                for m in msgs:
                    role = (m.get("role") or "user").lower()
                    content_val = m.get("content") or ""
                    _render_msg(m)
                    for tc in m.get("tool_calls") or []:
                        nm = tc.get("name") or "tool"
                        with st.expander(f"🔧 {nm}"):
                            st.json(tc.get("arguments"))
            else:
                _render_input_fallback(attrs, "input.value")
        elif kind == "TOOL":
            tp = canon(attrs, "tool.parameters")
            st.markdown("**工具参数：**")
            if tp is None:
                st.caption("（未捕获参数）")
            elif isinstance(tp, str):
                try:
                    st.json(json.loads(tp))
                except (json.JSONDecodeError, TypeError):
                    st.code(tp)
            else:
                st.json(tp)
        else:
            _render_input_fallback(attrs, "input.value")

    with c_out:
        st.markdown('<div class="io-col-head out-head">⬆  输出</div>', unsafe_allow_html=True)
        if kind == "LLM":
            msgs = to_messages(canon(attrs, "messages.output"))
            if msgs:
                for m in msgs:
                    role = (m.get("role") or "assistant").lower()
                    content_val = m.get("content") or ""
                    _render_msg(m)
            else:
                _render_input_fallback(attrs, "output.value")
        elif kind == "TOOL":
            tout = canon(attrs, "tool.output")
            if tout is None:
                st.caption("（未捕获返回结果）")
            elif isinstance(tout, (dict, list)):
                st.json(tout)
            elif isinstance(tout, str):
                try:
                    parsed = json.loads(tout)
                    if isinstance(parsed, (dict, list)):
                        st.json(parsed)
                    else:
                        st.code(str(parsed))
                except (json.JSONDecodeError, TypeError):
                    if len(tout) > 6000:
                        st.code(tout[:6000] + "...truncated")
                    else:
                        st.code(tout)
            else:
                st.code(str(tout))
        else:
            _render_input_fallback(attrs, "output.value")

    # --- Token breakdown (LLM) ----------------------------------------------
    if kind == "LLM":
        items = [
            ("输入 token",      canon(attrs, "tokens.input")),
            ("输出 token",     canon(attrs, "tokens.output")),
            ("总计 token",      canon(attrs, "tokens.total")),
            ("缓存读取 token", canon(attrs, "tokens.cache_read")),
            ("思考 token",  canon(attrs, "tokens.reasoning")),
        ]
        shown = [(k, v) for k, v in items if v is not None]
        if shown:
            cols = st.columns(min(5, len(shown)))
            for col, (k, v) in zip(cols, shown):
                col.metric(k, _format_tokens(v))
        cost = _estimate_cost(span, "tokens")
        if cost is not None:
            st.caption(f"💰 estimated cost (this span): **${cost:.4f}**")

    # --- Flow state (events log) --------------------------------------------
    events = span.get("events") or []
    with st.expander(f"⏱  Flow state ({len(events)} event(s))", expanded=False):
        if not events:
            st.caption("（未记录 span 事件）")
        else:
            for i, evt in enumerate(events):
                if not isinstance(evt, dict):
                    continue
                ename = evt.get("name", "(event)")
                ets = int(evt.get("time", 0))
                eattrs = evt.get("attributes") or {}
                with st.container():
                    st.markdown(
                        f'<div style="font-size:12px;color:#9ca3af;margin-bottom:4px">' +
                        f'<b style="color:#e5e7eb">{_esc(ename)}</b>  ·  ' +
                        f'{_esc(_format_ts_ms(ets)) if ets else ""}</div>',
                        unsafe_allow_html=True,
                    )
                    if eattrs:
                        st.json(eattrs)

    # --- Error block (only if span errored) ---------------------------------
    if is_err and err:
        st.markdown("#### ⚠ 错误")
        head_bits = []
        if err["exception_type"]:
            head_bits.append(f"<b>{_esc(err['exception_type'])}</b>")
        if err["status_message"]:
            head_bits.append(_esc(err["status_message"]))
        st.markdown(
            f'<div class="callout-err">'
            f'<div>{" &nbsp;·&nbsp; ".join(head_bits) or "(no message)"}</div></div>',
            unsafe_allow_html=True,
        )
        if err["stack"]:
            st.markdown("**堆栈信息：**")
            st.code(err["stack"], language="text")


def _render_input_fallback(attrs, key):
    """Smart fallback for input/output values."""
    val = attrs.get(key)
    if val is None:
        st.caption(f"（未捕获 {key.split(chr(46))[0]} ）")
        return
    if isinstance(val, str):
        parsed = None
        try:
            cand = json.loads(val)
            if isinstance(cand, (dict, list)):
                parsed = cand
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = None
        if parsed is not None:
            st.json(parsed)
        elif len(val) > 800:
            st.code(val[:800])
            st.caption("…（被截断）")
        else:
            st.code(val)
    else:
        st.json(val)


def _render_feedback_tab(span: dict) -> None:
    """Feedback scores.

    The agent_monitor SDK does not yet record feedback scores; this tab is a
    placeholder that follows the LangSmith / Langfuse UX convention. Any
    feedback captured under ``metadata.feedback`` / ``feedback.*`` attrs is
    surfaced; otherwise we show the empty state.
    """
    attrs = span.get("attributes") or {}
    feedback: list = []
    # Common conventions:
    fb = attrs.get("feedback") or attrs.get("feedbacks")
    if isinstance(fb, list):
        feedback = [x for x in fb if isinstance(x, dict)]
    elif isinstance(fb, dict):
        feedback = [fb]
    # Legacy single-score attrs
    if not feedback:
        score = attrs.get("feedback.score") or attrs.get("score")
        if score is not None:
            feedback.append({"name": "score", "value": score})
    if not feedback:
        st.markdown(
            '<div class="detail-card" style="text-align:center;color:#9ca3af;'
            'padding:30px 16px;">'
            '<div style="font-size:30px;">⭐</div>'
            '<div style="margin-top:6px;">尚未记录反馈分数。</div>'
            '<div style="margin-top:4px;font-size:11px;">'
            '一旦对该运行评分，分数会自动出现在这里。'
            '</div></div>',
            unsafe_allow_html=True,
        )
        return
    for fb in feedback:
        with st.container():
            st.markdown(
                f'<div class="detail-card">'
                f'<b>{_esc(fb.get("name", "feedback"))}</b>  '
                f'<span style="color:#9ca3af">{_esc(fb.get("comment", ""))}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            cols = st.columns(3)
            cols[0].metric("Score", str(fb.get("value", "-")))
            cols[1].metric("Source", str(fb.get("source", "-")))
            cols[2].metric("At", _format_ts(fb.get("timestamp") or 0))


def _render_metadata_tab(span: dict) -> None:
    start_ns = int(span.get("start_time", 0))
    end_ns = int(span.get("end_time", 0))
    dur_ms = (end_ns - start_ns) / 1_000_000
    attrs = span.get("attributes") or {}

    st.markdown(
        '<div class="detail-card"><div class="detail-head">基本信息</div>',
        unsafe_allow_html=True,
    )
    rows = [
        ("Trace ID", span.get("trace_id", "")),
        ("Span ID", span.get("span_id", "")),
        ("父 Span ID", span.get("parent_span_id") or "(根 span)"),
        ("服务", span.get("service_name") or "-"),
        ("法案版本", str(span.get("schema_version", "-"))),
        ("Name", span.get("name", "-")),
    ]
    sid = canon(attrs, "session.id")
    uid = canon(attrs, "user.id")
    model = canon(attrs, "model")
    provider = canon(attrs, "model.provider")
    tags = canon(attrs, "tags")
    if sid:
        rows.append(("会话 / 主题", sid))
    if uid:
        rows.append(("用户", uid))
    if model:
        rows.append(("Model", f"{model}" + (f"  ({provider})" if provider else "")))
    if tags:
        if isinstance(tags, list):
            rows.append(("标签", ", ".join(str(t) for t in tags)))
        else:
            rows.append(("标签", str(tags)))
    kv = '<div class="detail-kv">'
    for k, v in rows:
        kv += f'<div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div>'
    kv += "</div>"
    st.markdown(kv, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="detail-card"><div class="detail-head">Timing</div>',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("总时长", _format_duration_ms(dur_ms))
    m2.metric("Start", _format_ts(start_ns))
    m3.metric("End", _format_ts(end_ns))
    m4.metric("Span ID", (span.get("span_id", "") or "")[:8] + "…")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="detail-card"><div class="detail-head">全部属性（过滤后）</div>',
        unsafe_allow_html=True,
    )
    st.json(filter_visible_attrs(attrs, show_raw=False))
    with st.expander("Raw attributes (unfiltered)"):
        st.json(attrs)
    st.markdown("</div>", unsafe_allow_html=True)

    if span.get("events"):
        st.markdown(
            '<div class="detail-card"><div class="detail-head">Span 事件</div>',
            unsafe_allow_html=True,
        )
        st.json(span.get("events"))
        st.markdown("</div>", unsafe_allow_html=True)


# ===========================================================================
# RIGHT panel - metadata indicator panel
def _render_span_meta(span: dict) -> None:
    attrs = span.get("attributes") or {}
    kind = span_kind(attrs)
    name = _span_display_name(span)
    status = str(span.get("status", "")).upper()
    label, cls = _status_label(status)
    start_ns = int(span.get("start_time", 0))
    end_ns = int(span.get("end_time", 0))
    dur_ms = (end_ns - start_ns) / 1_000_000
    tin = canon(attrs, "tokens.input")
    tout = canon(attrs, "tokens.output")
    ttot = canon(attrs, "tokens.total") or (
        (tin + tout) if isinstance(tin, int) and isinstance(tout, int) else None
    )
    model = canon(attrs, "model") or "-"
    provider = canon(attrs, "model.provider") or ""
    cost = _estimate_cost(span, "tokens")

    rows = [
        ("名称", name),
        ("类型", kind),
        ("Model", f"{model}" + (f"  ({provider})" if provider else "")),
        ("Status", ""),
        ("Start", _format_ts_ms(start_ns)),
        ("End",   _format_ts_ms(end_ns)),
        ("耗时", _format_duration_ms(dur_ms)),
    ]
    st.markdown(
        f'<div style="margin-bottom:6px">'
        f'<span class="meta-pill {cls}">{_esc(label)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    for k, v in rows:
        if k == "Status":
            continue  # already shown above
        st.markdown(
            f'<div class="meta-kv strong">'
            f'<div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    # Tokens
    if ttot is not None:
        st.markdown(
            f'<div class="meta-kv strong">'
            f'<div class="k">Tokens</div><div class="v">{_esc(_format_tokens(ttot))}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif tin is not None or tout is not None:
        st.markdown(
            f'<div class="meta-kv strong">'
            f'<div class="k">输入 / 输出</div>'
            f'<div class="v">{_esc(_format_tokens(tin))} / {_esc(_format_tokens(tout))}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    # Cost (LLM)
    if cost is not None:
        st.markdown(
            f'<div class="meta-kv strong">'
            f'<div class="k">Cost</div><div class="v">${cost:.4f}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ===========================================================================
# 3-column body
# ===========================================================================
_dbg(f"BODY: sel_tid={st.session_state.selected_trace!r}, sel_spans count={len(sel_spans)}, first span kind={sel_spans[0].get("kind") if sel_spans else None!r}")
if not sel_spans:
    st.info("当前 trace 中没有 span，请运行你的 agent 后刷新。")
    st.stop()

_render_flowchart_mode(
    sel_spans,
    kpi,
    all_by_id={s['span_id']: s for s in sel_spans},
)
