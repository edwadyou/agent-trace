# -*- coding: utf-8 -*-
"""Replace remaining list body with single call to _render_flowchart_mode."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

# Find the NEW_BODY (which is 5 lines: _render_flowchart_mode(...)) -- keep
# Then find the leftover list body and delete it
# The leftover starts with "    def _select_only" (line 1841)

new_body_start = None  # 1-indexed line of "_render_flowchart_mode(" call
for i, l in enumerate(lines):
    if l.strip() == "_render_flowchart_mode(":
        new_body_start = i + 1
        break

# Find the next blank line after new_body (end of NEW_BODY)
new_body_end = new_body_start - 1 + 5  # 5 lines for NEW_BODY
# After that, find the leftover list body. It starts with "    def _select_only" or similar
# It ends with "with col_meta: ... _render_metadata_panel(...)\n)" 
# The leftover body has ~50 lines

# Find the start of the leftover (first "    def _select_only" after new_body_end)
leftover_start = None
for i in range(new_body_end, len(lines)):
    if "_select_only" in lines[i]:
        leftover_start = i + 1
        break

# Find the end: walk past all indented lines
leftover_end = leftover_start
while leftover_end < len(lines) and (lines[leftover_end].startswith(" ") or lines[leftover_end].strip() == ""):
    leftover_end += 1
# Now we are at the next non-indented non-blank line
print(f"NEW_BODY: L{new_body_start} to L{new_body_end}")
print(f"Leftover body: L{leftover_start} to L{leftover_end - 1}")
print(f"Leftover last line: {lines[leftover_end - 1][:80]!r}")
print(f"After leftover: {lines[leftover_end][:80]!r}")

# Delete leftover body (and the blank line before it)
# Actually: we want to delete from blank line before "    def _select_only" to end of col_meta block
# The col_meta block ends with ")" at column 0
# Let me find that
# leftover_end is already past col_meta block ending. Let me check.
# Actually we want to delete from blank line BEFORE _select_only through col_meta close + )

# For safety: delete from the line BEFORE _select_only through the col_meta closing ")" + 1 line after
del_start = leftover_start - 2  # the blank line before
# Find the "with col_meta:" close
col_meta_idx = None
for i in range(leftover_start, len(lines)):
    if "with col_meta:" in lines[i]:
        col_meta_idx = i
        break
print(f"col_meta_idx: L{col_meta_idx}")
# Walk from col_meta_idx to find the closing ")" at column 0
close_idx = col_meta_idx
while close_idx < len(lines) and lines[close_idx].strip() != ")":
    close_idx += 1
print(f"close_idx: L{close_idx+1}")

# Delete from del_start to close_idx + 1 (exclusive)
end_excl = close_idx + 1
print(f"Deleting 0-idx {del_start} to {end_excl - 1} ({end_excl - del_start} lines)")
del lines[del_start:end_excl]

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"Final: {len(lines)} lines")
