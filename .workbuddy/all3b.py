# -*- coding: utf-8 -*-
"""Phase 8 v2: smart _render_input_fallback replacement."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# Find old function and replace
old_fn_start = "def _render_input_fallback(attrs: dict, key: str) -> None:\n    val = attrs.get(key)\n    if val is None:\n        st.caption(f\"(no {key.split(chr(46))[0]} captured)\")\n        return\n    if isinstance(val, str):\n        if len(val) > 4000:\n"
assert old_fn_start in content, "old fn start not found"
start_idx = content.find(old_fn_start)

# Find end of function: 4-space-indent dedent (next def or class)
end_anchor = "\n\n\n\ndef _render_feedback_tab"
assert end_anchor in content, "end anchor not found"
end_idx = content.find(end_anchor, start_idx) + 1  # keep the leading newline

new_fn = (
    "def _render_input_fallback(attrs: dict, key: str) -> None:\n"
    "    \"\"\"Smart fallback for input/output values.\n\n"
    "    If `val` is a JSON string we parse and render via st.json() for\n"
    "    structure; otherwise we fall back to st.code() with truncation.\n"
    "    \"\"\"\n"
    "    val = attrs.get(key)\n"
    "    if val is None:\n"
    "        st.caption(f\"\uff08\u672a\u6355\u83b7 {key.split(chr(46))[0]} \uff09\")\n"
    "        return\n"
    "    if isinstance(val, str):\n"
    "        parsed = None\n"
    "        try:\n"
    "            cand = json.loads(val)\n"
    "            if isinstance(cand, (dict, list)):\n"
    "                parsed = cand\n"
    "        except (json.JSONDecodeError, TypeError, ValueError):\n"
    "            parsed = None\n"
    "        if parsed is not None:\n"
    "            st.json(parsed)\n"
    "        elif len(val) > 800:\n"
    "            st.code(val[:800])\n"
    "            st.caption(\"\u2026\uff08\u88ab\u622a\u65ad\uff09\")\n"
    "        else:\n"
    "            st.code(val)\n"
    "    else:\n"
    "        st.json(val)\n"
)

content = content[:start_idx] + new_fn + content[end_idx:]
print(f"Phase 8 v2: _render_input_fallback replaced")

open(p, "w", encoding="utf-8", newline="\n").write(content)