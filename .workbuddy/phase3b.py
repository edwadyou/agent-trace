# -*- coding: utf-8 -*-
"""Phase 3b: insert helpers (read from phase3a script), and remove list mode."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

# Read helpers from phase3a script (extract the helpers list)
phase3a = open(r"D:\my-projects\agent-monitor\.workbuddy\phase3a.py", encoding="utf-8").read()
# Extract the helpers list - between `helpers = []` and the end (before `print(f"\\nHelpers count: ...`)
import re
m = re.search(r"helpers = \[\]\n(.*?)\nhelpers\.append\(\"\"\)\nprint", phase3a, re.DOTALL)
if not m:
    print("Could not extract helpers from phase3a")
    sys.exit(1)
helpers_block = m.group(1)
# Parse: lines like  helpers.append("...")
helpers = []
for ln in helpers_block.splitlines():
    m2 = re.match(r'\s*helpers\.append\("(.*)"\)\s*$', ln)
    if m2:
        # decode \uXXXX and \\n etc.
        raw = m2.group(1)
        # Use codecs to decode escape sequences
        import codecs
        try:
            decoded = codecs.decode(raw, "unicode_escape")
        except Exception:
            decoded = raw
        helpers.append(decoded)
    else:
        print("Skipped line:", ln[:60])

print(f"Loaded {len(helpers)} helper lines")

# === Step 4: insert helpers before L1067 (left tree section) ===
# Find exact line
left_tree_line = None
for i, l in enumerate(lines):
    if "LEFT tree renderer" in l:
        left_tree_line = i + 1
        break
assert left_tree_line == 1067, f"Expected L1067, got L{left_tree_line}"

# Insert helpers BEFORE this line (don't replace the comment itself)
lines[left_tree_line - 1:left_tree_line - 1] = helpers
print(f"Step 4: inserted {len(helpers)} helper lines before L{left_tree_line}")


# === Step 5: insert view-mode switcher BEFORE "# Build filtered span list" ===
# Find it
build_filtered_line = None
for i, l in enumerate(lines):
    if l.startswith("# Build filtered span list"):
        build_filtered_line = i + 1
        break

radio = []
radio.append("")
radio.append("# ---------------------------------------------------------------------------")
radio.append("# View-mode switcher (will be removed in list-mode cleanup)")
radio.append("# ---------------------------------------------------------------------------")
radio.append("st.session_state.setdefault('view_mode', '\u5217\u8868')")
radio.append("_view_opts = ['\u5217\u8868', '\u6d41\u7a0b\u56fe']")
radio.append("_view_idx = _view_opts.index(st.session_state.view_mode) if st.session_state.view_mode in _view_opts else 0")
radio.append("st.radio(")
radio.append("    '\u89c6\u56fe\u6a21\u5f0f',")
radio.append("    options=_view_opts,")
radio.append("    index=_view_idx,")
radio.append("    horizontal=True,")
radio.append("    key='view_mode',")
radio.append("    label_visibility='collapsed',")
radio.append(")")
radio.append("")

lines[build_filtered_line - 1:build_filtered_line - 1] = radio
print(f"Step 5: inserted {len(radio)} radio lines before L{build_filtered_line}")


# === Step 11: remove list mode entirely ===
# Find these AFTER the insertions (line numbers shifted)
# Re-find
col_tree_line = None
three_col_body = None
render_tree_start = None
render_tree_end = None
render_metadata_start = None
render_metadata_end = None
view_mode_endif = None
expanded_spans_line = None
input_block_start = None
input_block_end = None
output_block_start = None
output_block_end = None

# Walk through and find the new positions
in_input_block = False
in_output_block = False
in_render_tree = False
in_render_metadata = False

for i, l in enumerate(lines):
    if "if st.session_state.view_mode ==" in l and view_mode_endif is None:
        view_mode_endif = i + 1
    if "col_tree, col_detail, col_meta = st.columns" in l and col_tree_line is None:
        col_tree_line = i + 1
    if l.startswith("# ==========================================================================="):
        if "3-column body" in lines[i + 1] if i + 1 < len(lines) else "":
            three_col_body = i + 1
    if l.startswith("def _render_tree(") and render_tree_start is None:
        render_tree_start = i + 1
        in_render_tree = True
    if in_render_tree and (l.startswith("def ") or l.startswith("# ===")) and render_tree_end is None and not l.startswith("def _render_tree"):
        render_tree_end = i
        in_render_tree = False
    if l.startswith("def _render_metadata_panel(") and render_metadata_start is None:
        render_metadata_start = i + 1
        in_render_metadata = True
    if in_render_metadata and (l.startswith("def ") or l.startswith("# ===")) and render_metadata_end is None and not l.startswith("def _render_metadata_panel"):
        render_metadata_end = i
        in_render_metadata = False
    if 'st.session_state.setdefault("expanded_spans"' in l and expanded_spans_line is None:
        expanded_spans_line = i + 1

print(f"\nFound positions (1-indexed):")
print(f"  view_mode_endif: {view_mode_endif}")
print(f"  col_tree: {col_tree_line}, three_col_body: {three_col_body}")
print(f"  render_tree: {render_tree_start}..{render_tree_end}")
print(f"  render_metadata: {render_metadata_start}..{render_metadata_end}")
print(f"  expanded_spans: {expanded_spans_line}")


# Apply deletions in REVERSE order to preserve indices
# 1. Delete _render_metadata_panel
if render_metadata_start and render_metadata_end:
    # Include the blank line before
    s = render_metadata_start - 2
    e = render_metadata_end  # exclusive
    print(f"\nDeleting _render_metadata_panel (L{s+1}-L{e}, {e-s} lines)")
    del lines[s:e]

# 2. Delete _render_tree (keep # LEFT tree renderer comment as it's the start marker)
# Actually delete the whole # === block + def onwards
if render_tree_start and render_tree_end:
    # Start: 2 lines before the def (the ======== comment block ends)
    s = render_tree_start - 4  # include the comment block
    e = render_tree_end  # exclusive
    print(f"Deleting _render_tree (L{s+1}-L{e}, {e-s} lines)")
    del lines[s:e]

# Re-find col_tree and view_mode after deletions
col_tree_line = None
view_mode_endif = None
expanded_spans_line = None
for i, l in enumerate(lines):
    if "if st.session_state.view_mode ==" in l and view_mode_endif is None:
        view_mode_endif = i + 1
    if "col_tree, col_detail, col_meta = st.columns" in l and col_tree_line is None:
        col_tree_line = i + 1
    if 'st.session_state.setdefault("expanded_spans"' in l and expanded_spans_line is None:
        expanded_spans_line = i + 1

print(f"\nAfter deletions:")
print(f"  view_mode_endif: {view_mode_endif}, col_tree: {col_tree_line}")
print(f"  expanded_spans: {expanded_spans_line}")


# 3. Delete view_mode radio block (between view_mode_endif and the if check + col_tree)
# The view-mode radio block + if/else body needs to be removed
# Find: the if st.session_state.view_mode check
# The if-block ends at the matching `else: # \u6d41\u7a0b\u56fe mode` (which we'll keep) and the _render_flowchart_mode call
# So delete from `if st.session_state.view_mode == '\u5217\u8868':` to the line `all_by_id={s['span_id']: s for s in sel_spans},\n    )` (the closing paren)

# Re-find
if_start = None
flowchart_call_end = None
for i, l in enumerate(lines):
    if l.startswith("if st.session_state.view_mode ==") and if_start is None:
        if_start = i
    if if_start is not None and l.strip() == ")":
        flowchart_call_end = i + 1
        break

if if_start is not None and flowchart_call_end is not None:
    # Include the blank line before if
    s = max(0, if_start - 2)
    e = flowchart_call_end
    print(f"Deleting list body (L{s+1}-L{e}, {e-s} lines)")
    del lines[s:e]


# 4. Delete expanded_spans init
if expanded_spans_line:
    s = expanded_spans_line - 1
    e = expanded_spans_line
    print(f"Deleting expanded_spans init L{s+1}")
    del lines[s:e]


# 5. Delete the view-mode switcher radio block (added in Step 5)
# Find the section comment "# View-mode switcher" and delete through the closing `)`
for i, l in enumerate(lines):
    if l.startswith("# View-mode switcher"):
        radio_start = i
        # Find the closing `)` at column 0 (top-level)
        for j in range(i, min(i + 30, len(lines))):
            if lines[j] == ")":
                radio_end = j + 1
                break
        else:
            radio_end = i + 16
        # Also include the blank line before
        s = max(0, radio_start - 1)
        e = radio_end
        print(f"Deleting view-mode switcher (L{s+1}-L{e}, {e-s} lines)")
        del lines[s:e]
        break


# Save
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nFinal: {len(lines)} lines")