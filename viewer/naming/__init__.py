"""Framework-specific span-name translation rules.

Per-framework rules live in this subpackage. Each framework subpackage exports
either ``<NAME>_RULES`` (a list) or ``RULES`` (a list). ``ALL_FRAMEWORK_RULES``
gathers them in import order; first match wins.

Viewer.py calls :func:`friendly_name`. New frameworks are added by:

    1. Creating ``viewer/naming/<framework>.py`` with a ``RULES`` (or NAME_RULES) list
    2. Adding the import below

Nothing else needs to change.
"""
from __future__ import annotations
import re
from typing import Optional, TYPE_CHECKING

from ._base import NamingRule, DisplayFn

# Active frameworks - add to this list when shipping a new one
from . import langchain
from . import llama_index
from . import crewai
from . import smolagents
from . import autogen
from . import haystack
from . import openai_agents
from . import pydantic_ai


def _gather(module) -> list[NamingRule]:
    """Find the rules list in a module whether named ``RULES`` or ``<FRAMEWORK>_RULES``."""
    if hasattr(module, "RULES"):
        return list(getattr(module, "RULES"))
    for attr in dir(module):
        if attr.isupper() and attr.endswith("_RULES"):
            return list(getattr(module, attr))
    return []


ALL_FRAMEWORK_RULES: list[NamingRule] = []
ALL_FRAMEWORK_RULES.extend(_gather(langchain))
ALL_FRAMEWORK_RULES.extend(_gather(llama_index))
ALL_FRAMEWORK_RULES.extend(_gather(crewai))
ALL_FRAMEWORK_RULES.extend(_gather(smolagents))
ALL_FRAMEWORK_RULES.extend(_gather(autogen))
ALL_FRAMEWORK_RULES.extend(_gather(haystack))
ALL_FRAMEWORK_RULES.extend(_gather(openai_agents))
ALL_FRAMEWORK_RULES.extend(_gather(pydantic_ai))


def friendly_name(name: str, kind: str) -> tuple[str, bool]:
    """Translate framework-internal span.name -> (display_name, visible).

    Args:
        name: raw span.name from the JSONL (e.g. ``RunnableSequence``)
        kind: openinference.span.kind (uppercase, e.g. ``CHAIN``)

    Returns:
        ``(display_name, visible)``. If no rule matches, returns the original
        name and ``True`` (the framework-internal string passes through, but
        the sidekick UI lets the user toggle "Show framework details" off).
    """
    if not isinstance(name, str) or not name:
        return ("(unnamed)", True)

    kind_upper = (kind or "UNKNOWN").upper()
    for rule in ALL_FRAMEWORK_RULES:
        m = rule.pattern.match(name)
        if m is None:
            continue
        if rule.require_kind and rule.require_kind != kind_upper:
            continue
        if rule.computed is not None:
            return rule.computed(name, m, kind_upper)
        return (rule.display, rule.visible)

    # Fallback: pass original name through (Framework-internal string; no rule matched)
    return (name, True)


__all__ = ["NamingRule", "ALL_FRAMEWORK_RULES", "friendly_name"]
