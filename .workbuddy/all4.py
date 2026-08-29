# -*- coding: utf-8 -*-
"""Phase 11: remove list mode completely."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()
lines = content.splitlines()

# Collect deletions (0-indexed inclusive)
deletions = []

# 1) view-mode switcher block (1-idx L1043-1056)
deletions.append((1042, 1055))

# 2) expanded_spans init (1-idx L720 = 0-idx 719)
deletions.append((719, 719))

# 3) _render_tree function: find boundaries
for i, l in enumerate(lines):
    if l == "def _render_tree(spans_for_node: Iterable[dict], children_: dict, *, depth: int) -> None:":
        fn_start = i
        # find end
        for j in range(i + 1, len(lines)):
            if lines[j].startswith("def ") or lines[j].startswith("# ===") or lines[j].startswith("# ---"):
                fn_end = j
                break
        deletions.append((fn_start - 1, fn_end - 1))  # include blank line before
        break

# 4) _render_metadata_panel function: find boundaries
for i, l in enumerate(lines):
    if l == "def _render_metadata_panel(trace_kpi: TraceKPI, all_spans: list, *, by_id_all: dict) -> None:":
        fn_start = i
        for j in range(i + 1, len(lines)):
            if lines[j].startswith("def ") or lines[j].startswith("# ===") or lines[j].startswith("# ---"):
                fn_end = j
                break
        deletions.append((fn_start - 1, fn_end - 1))  # include blank line before
        break

# 5) Body wrap if/else (1-idx L2285-L2329 originally, but lines shifted)
# Find: "if st.session_state.view_mode == '\u5217\u8868':"
# The if block extends until "else:  # \u6d41\u7a0b\u56fe mode" (which we'll keep but unindent)
# Then the _render_flowchart_mode call (unindent 4 spaces)
if_start = None
for i, l in enumerate(lines):
    if l.startswith("if st.session_state.view_mode == "):
        if_start = i
        break

if if_start is not None:
    # Find matching "else:" at the same indent (0 spaces)
    for j in range(if_start, len(lines)):
        if lines[j] == "else:  # \u6d41\u7a0b\u56fe mode":
            # Delete from if_start up to and including blank line before "else:"
            # but keep the _render_flowchart_mode(...) call block (after else:)
            # We need to also unindent the else: line and the call block
            else_idx = j
            # Find the closing ")" of _render_flowchart_mode call
            close_idx = None
            for k in range(else_idx, len(lines)):
                if lines[k] == "    )":
                    close_idx = k
                    break
            # Delete lines [if_start, else_idx-1) and unindent lines [else_idx, close_idx] by 4
            del lines[if_start:else_idx]
            close_idx -= (else_idx - if_start)
            else_idx = if_start
            for k in range(else_idx, close_idx + 1):
                if lines[k].startswith("    "):
                    lines[k] = lines[k][4:]
            print(f"Phase 11: list body removed; flowchart call unindented (close_idx={close_idx})")
            break

# Apply other deletions
for start, end in sorted(deletions, key=lambda x: -x[0]):
    print(f"Deleting 0-idx {start}-{end} (L{start+1}-L{end+1})")
    del lines[start:end + 1]

# Also remove all `st.session_state.expanded_spans = set()` assignment lines (3 places)
import re
new_lines = []
for l in lines:
    if re.match(r"^[ \t]*st\.session_state\.expanded_spans = set\(\)\s*$", l):
        continue
    new_lines.append(l)
removed = len(lines) - len(new_lines)
print(f"Removed {removed} expanded_spans assignments")
lines = new_lines

open(p, "w", encoding="utf-8", newline="\n").write(chr(10).join(lines) + chr(10))