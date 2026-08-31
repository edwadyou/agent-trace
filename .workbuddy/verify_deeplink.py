# -*- coding: utf-8 -*-
"""Deep-link regression: for every (trace, span), a fresh session loading
?trace=T&focus=S must end up with st.session_state.selected_span == S
(the single source of truth for the detail column)."""
import os
os.environ["TMPDIR"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TEMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TRACE_FILE"] = r"D:\agent\complex-agent-langchain\latest_traces.jsonl"

import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from collections import defaultdict
from streamlit.testing.v1 import AppTest

VIEWER = r"D:\my-projects\agent-monitor\viewer.py"

rows = []
with open(os.environ["TRACE_FILE"], encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))
by_trace = defaultdict(list)
for r in rows:
    by_trace[r["trace_id"]].append(r)
trace_ids = sorted(by_trace.keys())

fails, checked = [], 0
for tid in trace_ids:
    for s in by_trace[tid]:
        sid = s["span_id"]
        checked += 1
        at = AppTest.from_file(VIEWER)
        at.session_state["selected_trace"] = None       # simulate lost session
        at.query_params["trace"] = tid
        at.query_params["focus"] = sid
        at.run()
        got = at.session_state["selected_span"]
        if got != sid:
            fails.append((tid[:8], sid, got))
        if len(list(at.exception)) > 0:
            fails.append(("EXC", tid[:8], sid, [str(e)[:80] for e in at.exception]))

print(f"checked {checked} deep-link scenarios")
if fails:
    print(f"FAILURES: {len(fails)}")
    for f in fails[:30]:
        print("  ", f)
    sys.exit(1)
else:
    print("ALL PASS")
