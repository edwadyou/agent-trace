# -*- coding: utf-8 -*-
# Shared configuration / constants / CSS for the agent-monitor viewer.
# Split out of the original single-file `viewer.py`.
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

from viewer.canonical import SPAN_KINDS, COLORS
from viewer.normalize import canon, friendly_name, span_kind, to_messages
from viewer.visibility import is_span_visible, filter_visible_attrs

# Bidirectional mermaid-flowchart component (click a span node -> the detail

# column updates WITHOUT a full-page reload).  The frontend lives in

# flowchart_component/ and talks back through the v1 component postMessage

# protocol; the click handler sets Streamlit.setComponentValue which triggers

# a normal (no-navigation) rerun.

_COMPONENT_DIR = Path(__file__).resolve().parent.parent / "flowchart_component"

if (_COMPONENT_DIR / "index.html").is_file():

    _flowchart_component = components.declare_component(

        "agent_flowchart", path=str(_COMPONENT_DIR)

    )

else:

    _flowchart_component = None





# ---------------------------------------------------------------------------

# Bidirectional mermaid-flowchart component (click a span node -> the detail

# column updates WITHOUT a full-page reload).  The frontend lives in

# flowchart_component/ and talks back through the v1 component postMessage

# protocol; the click handler sends streamlit:setComponentValue which triggers

# a normal (no-navigation) rerun.

# ---------------------------------------------------------------------------

_COMPONENT_DIR = Path(__file__).resolve().parent.parent / "flowchart_component"

if (_COMPONENT_DIR / "index.html").is_file():

    _flowchart_component = components.declare_component(

        "agent_flowchart", path=str(_COMPONENT_DIR)

    )

else:

    _flowchart_component = None
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

except ImportError:

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



/* Scrollable wrapper around the trace list. Constrains the column to a

   viewport-relative height so the user can scroll through traces WITHOUT

   scrolling the page body — the center agent flow and right span

   detail panes stay fixed and visible. */

.st-key-trace_list_scroll {

    /* Sized by the "viewport-locked flex chain" at the bottom of this
       stylesheet instead of calc(100vh - <magic>px): flex-basis 0 + grow
       makes this box exactly as tall as the room its column has left, so
       the scrollbar always reaches the real end of the content.
       !important: Streamlit emits inline height/flex on this element when
       height="stretch" is set, which would otherwise win. */
    flex: 1 1 0% !important;

    height: auto !important;

    min-height: 0 !important;

    max-height: 100% !important;

    overflow-y: auto !important;

    overflow-x: hidden !important;

    padding: 4px 4px 6px 0;

    margin-top: 4px;

    scrollbar-width: thin;

    scrollbar-color: rgba(255,255,255,0.22) transparent;

}

.st-key-trace_list_scroll::-webkit-scrollbar { width: 6px; }

.st-key-trace_list_scroll::-webkit-scrollbar-thumb {

    background: rgba(255,255,255,0.20);

    border-radius: 3px;

}

.st-key-trace_list_scroll::-webkit-scrollbar-thumb:hover {

    background: rgba(255,255,255,0.35);

}

.st-key-trace_list_scroll::-webkit-scrollbar-track { background: transparent; }

/* ----- viewport-locked 3-column layout (so the side columns are the only
   things that scroll, not the whole page) -----
   Why: without these rules a tall detail panel pushes the body height
   past the viewport and Streamlit shows a page-level scrollbar; the user
   then ends up scrolling the entire app instead of the right column.
   The three columns share whatever vertical room the page-header did not
   take, so left/right can scroll independently and the middle
   (Mermaid) column keeps the height the component reports.

   The height plumbing itself lives in the "viewport-locked flex chain"
   block at the bottom of this stylesheet: it measures the room that is
   really left over instead of estimating it in pixels. The old blanket
   max-height: calc(100vh - 130px) assumed a fixed page-header height and
   silently clipped whatever did not fit. */

[data-testid="stHorizontalBlock"] { align-items: stretch; }

/* ----- right detail scroll container (mirror of trace list) ----- */
.st-key-detail_scroll {

    /* Sized by the "viewport-locked flex chain" at the bottom of this
       stylesheet instead of calc(100vh - <magic>px).

       This is the box the user scrolls, and it sits BELOW a
       variable-height stack: the panel title, plus the back-to-overview
       button that only renders once a non-root span is selected. A fixed
       calc() cannot know how tall that stack is, so when the button
       appeared the panel overflowed its clipped ancestors and its tail
       became unreachable - the scrollbar hit the end while content was
       still hidden. flex-basis 0 + grow measures the leftover room.

       !important: Streamlit emits inline height/flex on this element when
       height="stretch" is set, which would otherwise win. */
    flex: 1 1 0% !important;

    height: auto !important;

    min-height: 0 !important;

    max-height: 100% !important;

    overflow-y: auto !important;

    overflow-x: hidden !important;

    padding: 4px 4px 6px 0;

    margin-top: 4px;

    scrollbar-width: thin;

    scrollbar-color: rgba(255,255,255,0.22) transparent;

}
.st-key-detail_scroll::-webkit-scrollbar { width: 6px; }
.st-key-detail_scroll::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.20);
    border-radius: 3px;
}
.st-key-detail_scroll::-webkit-scrollbar-thumb:hover {
    background: rgba(255,255,255,0.35);
}
.st-key-detail_scroll::-webkit-scrollbar-track { background: transparent; }




/* Each trace is rendered as a Streamlit button whose key is

   `trace_card_<tid>`. Streamlit turns that key into the wrapper class

   `st-key-trace_card_<sanitized_tid>` on the element container. We

   style that container as a compact card. The previous empty

   `<div class="trace-card">` HTML wrappers were broken (the button

   rendered as a sibling, not a child) and have been removed. */

[data-testid="stElementContainer"][class*="st-key-trace_card_"] {

    background: rgba(255,255,255,0.09);

    border: 1px solid rgba(255,255,255,0.20);

    border-radius: 6px;

    padding: 0;

    margin: 0 0 4px 0;

    transition: background 0.15s ease, border-color 0.15s ease;

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"]:hover {

    background: rgba(255,255,255,0.13);

    border-color: rgba(255,255,255,0.32);

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"] [data-testid="stButton"] {

    margin: 0;

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"] button {

    padding: 4px 10px !important;

    font-size: 12px !important;

    line-height: 1.2 !important;

    min-height: 26px !important;

    border: none !important;

    text-align: left;

    font-family: ui-monospace, "JetBrains Mono", "Cascadia Code", Consolas, monospace !important;

    width: 100%;

    white-space: nowrap;

    overflow: hidden;

    text-overflow: ellipsis;

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"] button[data-testid="stBaseButton-secondary"] {

    background: transparent !important;

    /* Follow the active Streamlit text color. A hard-coded light gray was

       nearly invisible when the app ran with a light page background. */

    color: var(--text-color, #1f2937) !important;

    font-weight: 600 !important;

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"] button[data-testid="stBaseButton-secondary"]:hover {

    background: rgba(255,255,255,0.08) !important;

    color: var(--text-color, #111827) !important;

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"] button:focus-visible {

    outline: 1px solid rgba(59,130,246,0.55);

    outline-offset: -1px;

}



/* Active (primary) trace button — subtle blue accent so it stands out

   from the secondary cards without clashing with the dark theme. */

[data-testid="stElementContainer"][class*="st-key-trace_card_"] button[data-testid="stBaseButton-primary"] {

    background: rgba(59,130,246,0.22) !important;

    color: var(--primary-color, #1d4ed8) !important;

    font-weight: 700 !important;

}

[data-testid="stElementContainer"][class*="st-key-trace_card_"]:has(button[data-testid="stBaseButton-primary"]) {

    border-color: rgba(59,130,246,0.65);

    background: rgba(59,130,246,0.10);

}



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

/* Keep the span-detail tab switcher visible while its long payload scrolls.
   The title itself is rendered outside detail_scroll, so only this nav row
   needs to stick. top:-4px cancels the scroll container's top padding so
   content cannot peek through the gap above the solid header background. */
.st-key-detail_scroll [data-testid="stTabs"] div:has(> [data-testid="stTab"]) {
    position: sticky !important;
    top: -4px !important;
    z-index: 20 !important;
    background: var(--background, #fff) !important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
}

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

    /* ===== 页面锁死：整页固定不滚动，只有左右栏内部滚动 ===== */
    /* ===== viewport-locked flex chain =====
       The page itself never scrolls; only the two side panels do. Every
       level between the page shell and those panels is a flex column that
       hands its REAL height down, and the panels are flex: 1 1 0% so they
       end up exactly as tall as the space left over.

       Why this replaced the old pixel guesses: the previous rules locked
       the panels to calc(100vh - 200px) and every column to
       max-height: calc(100vh - 130px), i.e. they hard-coded the height of
       everything stacked above them (page header, panel title, container
       padding). Those guesses broke as soon as the real stack was taller -
       most reliably when the conditional back-to-overview button appears,
       which is exactly when a non-root span is selected and the user is
       reading a long payload. The panel then overflowed ancestors that all
       had overflow: hidden, and since the page cannot scroll either, the
       tail was permanently unreachable: the scrollbar ran out while content
       was still hidden. Measuring with flexbox removes the guess.

       :has() is used on purpose so these rules do not depend on how many
       wrapper elements Streamlit inserts between levels, which varies by
       version (stElementContainer / stLayoutWrapper / stVerticalBlock). */

    [data-testid="stMain"] {
        /* flex-shrink + min-height:0 keep this correct even if a future
           Streamlit version puts an in-flow header above stMain: the box
           then shrinks to the real leftover space instead of overflowing
           the viewport by the header height. */
        flex: 1 1 auto !important;
        min-height: 0 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* Streamlit may wrap .block-container in an extra level; whatever that
       level is, it has to pass the full height down. */
    [data-testid="stMain"] > :has(.block-container) {
        flex: 1 1 0% !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
    }

    .block-container {
        flex: 1 1 0% !important;
        min-height: 0 !important;
        height: auto !important;
        max-height: 100% !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* every box on the path down to a side panel stretches and stays a flex
       column. The row and column boxes are excluded (styled below) and so
       are the two panel containers (the scrolling leaves, styled above). */
    .block-container *:has(.st-key-detail_scroll):not([data-testid="stHorizontalBlock"]):not([data-testid="stColumn"]):not(.st-key-detail_scroll):not(.st-key-trace_list_scroll),
    .block-container *:has(.st-key-trace_list_scroll):not([data-testid="stHorizontalBlock"]):not([data-testid="stColumn"]):not(.st-key-detail_scroll):not(.st-key-trace_list_scroll) {
        flex: 1 1 0% !important;
        min-height: 0 !important;
        max-height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: visible !important;
    }

    /* the 3-column body row is the one that owns the detail panel; it takes
       all the room the page-header row left */
    [data-testid="stHorizontalBlock"]:has(.st-key-detail_scroll) {
        flex: 1 1 0% !important;
        min-height: 0 !important;
        max-height: 100% !important;
        align-items: stretch !important;
    }

    /* every other row (the page-header row, and rows nested inside the
       panels) keeps its natural content height */
    [data-testid="stHorizontalBlock"]:not(:has(.st-key-detail_scroll)) {
        flex: 0 0 auto !important;
    }

    /* the columns of the body row fill their row exactly. Scoped with :has()
       on the owning row instead of a blanket [data-testid="stColumn"]: the
       blanket version leaked onto the small nested columns inside the panels
       (st.columns(2) for input/output, st.columns(4) for the metadata grid)
       and clipped them. Replaces the old max-height: calc(100vh - 130px). */
    [data-testid="stHorizontalBlock"]:has(.st-key-detail_scroll) > [data-testid="stColumn"] {
        height: 100% !important;
        min-height: 0 !important;
        overflow: hidden !important;
    }

    /* the two side columns are the flex parents of their own title/button
       stack plus their scrolling panel */
    [data-testid="stColumn"]:has(.st-key-detail_scroll),
    [data-testid="stColumn"]:has(.st-key-trace_list_scroll) {
        display: flex !important;
        flex-direction: column !important;
    }

    /* the center (Mermaid) column scrolls instead of clipping when the
       diagram is taller than the row */
    [data-testid="stHorizontalBlock"]:has(.st-key-detail_scroll) > [data-testid="stColumn"]:not(:has(.st-key-detail_scroll)):not(:has(.st-key-trace_list_scroll)) {
        overflow-y: auto !important;
    }

    /* Streamlit puts an inline height:100% on the block inside a
       stretch-height container. Inside a scroll box that block must be
       content-sized and must not clip, otherwise its overflow is invisible
       AND unreachable - the same scrollbar-stops-early symptom. This also
       replaces the old blanket rule that set max-height: 100vh plus
       overflow: hidden on EVERY stVerticalBlock, which clipped nested
       blocks all the way down inside the panels. */
    .st-key-detail_scroll [data-testid="stVerticalBlock"],
    .st-key-trace_list_scroll [data-testid="stVerticalBlock"] {
        height: auto !important;
        max-height: none !important;
        min-height: 0 !important;
        overflow: visible !important;
    }

    /* If this Streamlit version tags two nested levels with the same key
       class, only the outer one may scroll: the inner one stays a plain
       content-sized block so everything overflows into the outer scroll box
       instead of a second scrollbar fighting for the same space. */
    .st-key-detail_scroll .st-key-detail_scroll,
    .st-key-trace_list_scroll .st-key-trace_list_scroll {
        flex: 0 0 auto !important;
        height: auto !important;
        max-height: none !important;
        min-height: 0 !important;
        overflow: visible !important;
        padding: 0 !important;
        margin: 0 !important;
    }

</style>

"""

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
_DEFAULT_TRACE_PATHS = [

    Path(os.environ.get("TRACE_FILE", "")),

    Path("latest_traces.jsonl"),

    Path("D:/agent/complex-agent-langchain/latest_traces.jsonl"),

    Path("D:/my-projects/agent-monitor/latest_traces.jsonl"),

]
_MERMAID_MAX_NODES = 80

_NODE_LABEL_MAX_CHARS = 60
_TOOL_ENVELOPE_RE = re.compile(r"^\s*json\s*\n(.*)$", re.DOTALL)



_KNOWN_PAYLOAD_FIELDS = (

    "sub_claims", "claims", "subclaims", "steps",

    "facts", "items", "results", "documents",

    "sources", "evidence", "todos", "checklist",

)
