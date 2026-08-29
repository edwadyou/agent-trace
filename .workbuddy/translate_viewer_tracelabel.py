# -*- coding: utf-8 -*-
"""translate_viewer_tracelabel.py

Apply a deterministic set of literal English -> Chinese string replacements to
`viewer.py`.  This script is intentionally explicit: every replacement is written
as a literal ``old -> new`` pair using ``\\uXXXX`` escapes so the source is
ASCII-safe and unambiguous.

Run it explicitly with::

    python .workbuddy/translate_viewer_tracelabel.py

It rewrites ``viewer.py`` in place only if at least one substitution actually
matched.  A summary is printed to stdout.

NOTE: do not invoke this from any tooling that loads ``viewer.py``; run it by
hand only after reviewing the rule table.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Target file
# ---------------------------------------------------------------------------
VIEWER_PATH = Path(r"D:\my-projects\agent-monitor\viewer.py")

# ---------------------------------------------------------------------------
# Replacement table.
#
# Order matters: later rules see the file *after* earlier rules have already
# substituted.  ``# skipped per spec`` marks rules from the original brief that
# the spec said not to apply literally - they remain documented but produce no
# string change.
#
# All targets are written with explicit ``\uXXXX`` escapes so the source is
# pure ASCII and the codepoints are obvious.
# ---------------------------------------------------------------------------
REPLACEMENTS: list[tuple[str, str, str]] = [
    # -- Short English UI labels -> Chinese --------------------------------
    ("Parallel Branches",
        "\u591a\u4efb\u52a1\u5e76\u884c",
        "short label"),
    ("Parallel: ",
        "\u591a\u4efb\u52a1\u5e76\u884c\uff1a",
        "short prefix"),
    ("Parallel Search (",
        "\u591a\u4efb\u52a1\u5e76\u884c\uff08",
        "parallel search prefix"),
    ("Parallel: {_short_purpose(tools[0]) or tools[0]}",
        "\u591a\u4efb\u52a1\u5e76\u884c\uff1a{_short_purpose(tools[0]) or tools[0]}",
        "parallel single f-string"),
    ("Parallel: {a} + {b}",
        "\u591a\u4efb\u52a1\u5e76\u884c\uff1a{a} + {b}",
        "parallel pair f-string"),
    ("Parallel Search ({n})",
        "\u591a\u4efb\u52a1\u5e76\u884c\uff08{n}\uff09",
        "parallel search n f-string"),
    ("Tool Agent",
        "\u5de5\u5177\u578b\u667a\u80fd\u4f53",
        "tool agent"),
    ("Retrieval Chain",
        "\u68c0\u7d22\u94fe",
        "retrieval chain"),
    ("LLM Chain",
        "LLM \u8c03\u7528\u94fe",
        "llm chain"),
    ("LLM Call (templated)",
        "\u5927\u6a21\u578b\u8c03\u7528\uff08\u5e26\u6a21\u677f\uff09",
        "llm call templated"),
    ("LLM Call",
        "\u5927\u6a21\u578b\u8c03\u7528",
        "llm call"),
    ("Chain Step",
        "\u94fe\u8def\u6b65\u9aa4",
        "chain step"),
    ("(unnamed)",
        "\uff08\u672a\u547d\u540d\uff09",
        "unnamed"),
    ("(empty trace)",
        "\uff08\u7a7a trace\uff09",
        "empty trace"),

    # -- _fmt_trace_option separator --------------------------------------
    # The brief asked to swap U+8DEF (\u8def, "lu") + 2 spaces for
    # U+00B7 (middle dot) + 2 spaces.  If the file already uses the middle
    # dot this is a harmless no-op.
    ("\u8def  ",
        "\u00b7  ",
        "separator (U+8DEF -> U+00B7)"),
    # Twin safety rule for the four f-string fragments inside
    # _fmt_trace_option, in case only the joined form differs.
    ('f"\u8def  {',
        'f"\u00b7  {',
        "separator fragment in f-string"),

    # -- Status emoji lines ------------------------------------------------
    # viewer.py already stores the emojis directly; only the trailing
    # English comment needs translation.
    ('ico = "\u274c"  # red cross',
        'ico = "\u274c"  # \u7ea2\u8272\u53c9 (ERROR)',
        "ERROR comment"),
    ('ico = "\u2705"  # green tick',
        'ico = "\u2705"  # \u7eff\u8272\u52fe (OK)',
        "OK comment"),
    ('ico = "\u23f3"  # hourglass (UNSET / in-progress)',
        'ico = "\u23f3"  # \u6c99\u6f0f (UNSET)',
        "UNSET comment"),

    # Defensive fallbacks: translate the bare trailing comments even if
    # the surrounding ``ico = ...`` line has been refactored.
    ("  # red cross",
        "  # \u7ea2\u8272\u53c9 (ERROR)",
        "bare red-cross comment"),
    ("  # green tick",
        "  # \u7eff\u8272\u52fe (OK)",
        "bare green-tick comment"),
    ("  # hourglass (UNSET / in-progress)",
        "  # \u6c99\u6f0f (UNSET)",
        "bare hourglass comment"),

    # -- Not used literally (per original spec) ---------------------------
    # Kept as a single explicit no-op so reviewers see the rule was
    # considered.  ``')  if n == 1'`` -> ``')'`` was marked ``skip`` so we
    # deliberately do not apply it.
    ("__SKIP__: ')  if n == 1' -> '\\uff09'",
        "__SKIP__: ')  if n == 1' -> '\\uff09'",
        "skipped per spec"),
]


def _truncate(s: str, limit: int = 60) -> str:
    return s if len(s) <= limit else s[: limit - 3] + "..."


def apply_replacements(text: str) -> tuple[str, list[tuple[str, str, str, int]]]:
    """Run each rule and return ``(new_text, [(old, new, note, count), ...])``."""
    report: list[tuple[str, str, str, int]] = []
    for old, new, note in REPLACEMENTS:
        if old.startswith("__SKIP__"):
            report.append((old, new, note, 0))
            continue
        count = text.count(old)
        if count:
            text = text.replace(old, new)
        report.append((old, new, note, count))
    return text, report


def main() -> int:
    if not VIEWER_PATH.exists():
        print(f"[ERROR] viewer.py not found at {VIEWER_PATH}", file=sys.stderr)
        return 2

    original = VIEWER_PATH.read_text(encoding="utf-8")
    updated, report = apply_replacements(original)

    matched = [r for r in report if r[3] > 0]
    skipped = [r for r in report if r[0].startswith("__SKIP__")]
    unmatched = [r for r in report if r[3] == 0 and not r[0].startswith("__SKIP__")]

    print(f"Rules declared      : {len(report)}")
    print(f"Rules with matches  : {len(matched)}")
    print(f"Rules that no-oped  : {len(unmatched)}")
    print(f"Rules skipped       : {len(skipped)}")
    print(f"Total substitutions : {sum(r[3] for r in report)}")
    print()
    print("Detail:")
    for idx, (old, new, note, count) in enumerate(report, 1):
        marker = "SKIP" if old.startswith("__SKIP__") else ("HIT " if count else "miss")
        print(f"  [{idx:2}] {marker} n={count:<3} {note}")
        print(f"        old: {_truncate(old)!r}")
        print(f"        new: {_truncate(new)!r}")

    if updated == original:
        print()
        print("No changes would be made; viewer.py is already up to date.")
        return 0

    print()
    print(f"About to overwrite: {VIEWER_PATH}")
    print("Re-run with --apply to actually write the file.")
    if "--apply" not in sys.argv:
        return 0
    VIEWER_PATH.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Wrote {len(updated)} chars to {VIEWER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
