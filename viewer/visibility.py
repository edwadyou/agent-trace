"""Default visibility filter - decides which spans / attribute keys are hidden.

We pre-filter spans the user shouldn't normally see:
  * LangGraph plumbing (\\__start__ / \\__end__ / Channel ops / RunnableSequence wrappers)
  * OTel transport noise (telemetry.sdk.*, process.*, host.*, os.*)
  * Framework-internal metadata (langgraph_step / langgraph_node / langgraph_path)

Three sidebar toggles in viewer.py let the user override this:
  - ``hide_plumbing`` (default True): filters spans out of the tree entirely
  - ``show_original`` (default False): shows the raw span.name alongside the friendly label
  - ``show_raw`` (default False): exposes the unprocessed attributes dictionary
"""
from __future__ import annotations
import re


# ---------------------------------------------------------------------------
# Span.name patterns always hidden when hide_plumbing=True
# ---------------------------------------------------------------------------
HIDE_NAME_PATTERNS = [
    re.compile(r"^__start__$"),
    re.compile(r"^__end__$"),
    re.compile(r"^Channel(Read|Write)\b"),
    re.compile(r"^CallableBranch$"),
    re.compile(r"^_RoutedNode"),
    # Heavily nested Runnable wrappers (3+ levels deep)
    re.compile(r"^RunnableSequence\(RunnableSequence"),
]

# ---------------------------------------------------------------------------
# Attribute key patterns always hidden
# ---------------------------------------------------------------------------
HIDE_ATTR_PATTERNS = [
    re.compile(r"^langgraph_"),
    re.compile(r"^telemetry\.sdk\."),
    re.compile(r"^process\."),
    re.compile(r"^os\."),
    re.compile(r"^host\."),
    re.compile(r"^runtime\."),
    re.compile(r"^user_agent$"),
    re.compile(r"^http\."),          # url / status_code / method handled elsewhere
    # Set by OI itself, already used (we display them as their friendly form)
    re.compile(r"^openinference\."),
]


def is_span_visible(span: dict, *, show_all: bool = False) -> bool:
    """Decide if a span should appear in the tree under default filtering.

    Args:
        span:     dict with at least 'name' and 'attributes'
        show_all: if True, bypass filtering (used for the "Show framework details" toggle)

    Returns:
        bool
    """
    if show_all:
        return True
    name = (span.get("name") or "") if isinstance(span, dict) else ""
    for pat in HIDE_NAME_PATTERNS:
        if pat.match(name):
            return False
    return True


def filter_visible_attrs(attrs: dict, *, show_raw: bool = False) -> dict:
    """Strip plumbing keys from an attributes dict for display.

    If ``show_raw`` is True (user opened the Raw tab), keys are preserved.
    """
    if show_raw:
        return attrs or {}
    if not isinstance(attrs, dict):
        return {}
    return {
        k: v for k, v in attrs.items()
        if not any(pat.match(k) for pat in HIDE_ATTR_PATTERNS)
    }
