"""Base types for span-name translation rules.

Adding a new framework:
    1. Create viewer/naming/<framework>.py with ``<FRAMENAME>_RULES: list[NamingRule]``
    2. Import it in viewer/naming/__init__.py
    3. viewer.py auto-picks it up. No edits elsewhere.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable, Match, Optional


# (raw_name, regex_match, kind) -> (display, visible)
DisplayFn = Callable[[str, Match[str], str], tuple[str, bool]]


@dataclass(frozen=True)
class NamingRule:
    """One translation rule: regex name match -> friendly label.

    Attributes:
        pattern:      compiled regex to match against the raw span.name
        display:      static friendly label (used when computed is None)
        visible:      True = show by default, False = hide by default
        require_kind: only apply when span_kind() equals this uppercase value
                      (None = any kind)
        computed:     optional callable taking (raw_name, regex_match, kind)
                      and returning ``(display, visible)`` for dynamic labels
                      (e.g. "Parallel: web_search, knowledge_base")
    """
    pattern:      "re.Pattern[str]"
    display:      str = ""
    visible:      bool = True
    require_kind: Optional[str] = None
    computed:     Optional[DisplayFn] = None
