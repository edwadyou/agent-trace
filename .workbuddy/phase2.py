# -*- coding: utf-8 -*-
"""Phase 2: fix missed translations, then do major structural changes."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    content = f.read()

# Fix 5 missed translations (these have escape issues)
fixes = [
    ("Flow state ({len(events)} event(s))", "\u6d41\u7a0b\u4e8b\u4ef6\uff08{len(events)} \u6761\uff09"),
    ("Identity</div>", "\u57fa\u672c\u4fe1\u606f</div>"),
    ("All attributes (filtered)</div>", "\u5168\u90e8\u5c5e\u6027\uff08\u8fc7\u6ee4\u540e\uff09</div>"),
    ("Span events</div>", "Span \u4e8b\u4ef6</div>"),
]
for old, new in fixes:
    if old in content:
        content = content.replace(old, new, 1)
        print("  OK " + old[:40])
    else:
        print("  STILL MISSING: " + old[:40])

# Now find the current line numbers for major changes
lines = content.splitlines()
print("\nTotal lines after fix:", len(lines))

# Find anchors
anchors = {
    "left tree section": -1,
    "_render_tree def": -1,
    "_render_metadata_panel def": -1,
    "_render_run_tab def": -1,
    "_render_input_fallback def": -1,
    "old _render_msg": -1,
    "input block": -1,
    "output block": -1,
    "Build filtered span list": -1,
    "col_tree = st.columns": -1,
    "3-column body": -1,
}
for i, l in enumerate(lines):
    for k in anchors:
        needle = {
            "left tree section": "LEFT tree renderer",
            "_render_tree def": "def _render_tree(",
            "_render_metadata_panel def": "def _render_metadata_panel(",
            "_render_run_tab def": "def _render_run_tab(",
            "_render_input_fallback def": "def _render_input_fallback(",
            "old _render_msg": "def _render_msg(role: str, content: object)",
            "input block": "Input block (collapsible)",
            "output block": "Output block (collapsible)",
            "Build filtered span list": "Build filtered span list",
            "col_tree = st.columns": "col_tree, col_detail, col_meta = st.columns",
            "3-column body": "3-column body",
        }[k]
        if needle in l and anchors[k] < 0:
            anchors[k] = i + 1

for k, v in anchors.items():
    print("  L" + str(v) + ": " + k)

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)