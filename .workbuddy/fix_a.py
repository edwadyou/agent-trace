import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# === Phase A: add _select_trace helper (next to _jump_to_span / _clear_focus) ===
old_helpers = (
    "def _jump_to_span(span_id):\n"
    "    \"\"\"Set focus query param (and preserve trace).\"\"\"\n"
    "    st.query_params[\"focus\"] = span_id\n"
    "    st.rerun()\n"
    "\n"
    "\n"
    "def _clear_focus():\n"
    "    \"\"\"Clear focus query param, keep trace.\"\"\"\n"
    "    if \"focus\" in st.query_params:\n"
    "        del st.query_params[\"focus\"]\n"
    "    st.rerun()\n"
)
new_helpers = (
    "def _jump_to_span(span_id):\n"
    "    \"\"\"Set focus query param (and preserve trace).\"\"\"\n"
    "    st.query_params[\"focus\"] = span_id\n"
    "    st.rerun()\n"
    "\n"
    "\n"
    "def _clear_focus():\n"
    "    \"\"\"Clear focus query param, keep trace.\"\"\"\n"
    "    if \"focus\" in st.query_params:\n"
    "        del st.query_params[\"focus\"]\n"
    "    st.rerun()\n"
    "\n"
    "\n"
    "def _select_trace(tid):\n"
    "    \"\"\"Switch the active trace; clear any stale focus.\"\"\"\n"
    "    st.session_state.selected_trace = tid\n"
    "    if \"focus\" in st.query_params:\n"
    "        del st.query_params[\"focus\"]\n"
    "\n"
    "\n"
    "def _trace_start_ns(tid):\n"
    "    \"\"\"Earliest span start_time (ns) in the trace; 0 if empty.\"\"\"\n"
    "    spans = traces.get(tid) or []\n"
    "    if not spans:\n"
    "        return 0\n"
    "    return min(int(s.get(\"start_time\", 0)) for s in spans)\n"
)
if old_helpers in content:
    content = content.replace(old_helpers, new_helpers, 1)
    print("A: added _select_trace + _trace_start_ns helpers")
else:
    print("A: helpers block not found")

open(p, "w", encoding="utf-8", newline="\n").write(content)