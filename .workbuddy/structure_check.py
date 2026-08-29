# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
lines = content.splitlines()
print("Total lines:", len(lines))
print("Total bytes:", len(content.encode("utf-8")))

# Locate the new functions
markers = [
    ("def _mermaid_safe_id", "_mermaid_safe_id"),
    ("def _build_mermaid", "_build_mermaid"),
    ("def _render_mermaid_html", "_render_mermaid_html"),
    ("def _render_flowchart_mode", "_render_flowchart_mode"),
    ("if st.session_state.view_mode == ", "view_mode if/else"),
    ("c_in, c_out = st.columns", "IO side-by-side"),
]
for needle, label in markers:
    idx = content.find(needle)
    if idx > 0:
        ln = content[:idx].count(chr(10)) + 1
        print(f"  OK  L{ln}: {label}")
    else:
        print(f"  MISSING  {label}")

# Verify view_mode session_state default
if "st.session_state.setdefault('view_mode'" in content:
    print("  OK  view_mode session state default")

# Verify Mermaid CDN URL
if "mermaid@10/dist/mermaid.min.js" in content:
    print("  OK  Mermaid CDN URL")

# Verify query params usage
if "st.query_params.get('focus')" in content:
    print("  OK  st.query_params focus")

# Verify no stray old markers
stray = []
for needle in ["#### \U0001F50D Span Detail", "#### \U0001F4CA Metadata",
               "#### \U0001F50E Agent Trace Monitor", "(no parameters captured)",
               "(no result captured)", "(unnamed)", "(empty trace)"]:
    if needle in content:
        stray.append(needle)
print()
print("Stray English markers:", stray if stray else "(none)")

# Verify Chinese markers
chi = ["\u591a\u4efb\u52a1\u5e76\u884c", "\u5927\u6a21\u578b\u8c03\u7528", "\u5bfc\u822a\u6811",
       "\u8fd4\u56de\u5168\u8c8c", "\u805a\u7126", "view_mode", "io-col-head", "in-head", "out-head"]
for needle in chi:
    present = needle in content
    print("  " + ("OK  " if present else "MISS  ") + needle)

# Verify c_in/c_out variable names
for v in ["c_in, c_out = st.columns", "with c_in:", "with c_out:"]:
    present = v in content
    print("  " + ("OK  " if present else "MISS  ") + v)