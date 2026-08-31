# -*- coding: utf-8 -*-
"""Comprehensive AppTest verification: for every trace and every span,
clicking that span's node must make the span detail show exactly that span.

Two scenarios per (trace, span):
  A) session preserved: selected_trace=T (already on the trace), focus=S
  B) session lost (the reported bug): selected_trace=None + URL ?trace=T&focus=S
"""
import os
os.environ["TMPDIR"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TEMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TRACE_FILE"] = r"D:\agent\complex-agent-langchain\latest_traces.jsonl"

import sys
sys.stdout.reconfigure(encoding="utf-8")

from streamlit.testing.v1 import AppTest

VIEWER = r"D:\my-projects\agent-monitor\viewer.py"

# Discover traces + spans by importing the loader logic
import json
from collections import defaultdict

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
print(f"total traces: {len(trace_ids)}  total spans: {len(rows)}")

fails = []
checked = 0

for tid in trace_ids:
    spans = by_trace[tid]
    for s in spans:
        sid = s["span_id"]
        checked += 1

        # Scenario A: session preserved
        at = AppTest.from_file(VIEWER)
        at.session_state["selected_trace"] = tid
        try:
            at.query_params["focus"] = sid
        except Exception:
            pass
        at.run()
        got_a = at.session_state["selected_span"]
        if got_a != sid:
            fails.append(("A", tid[:8], sid, got_a))

        # Scenario B: session lost -> URL carries trace + focus
        at2 = AppTest.from_file(VIEWER)
        at2.session_state["selected_trace"] = None
        try:
            at2.query_params["trace"] = tid
            at2.query_params["focus"] = sid
        except Exception:
            pass
        at2.run()
        got_b = at2.session_state["selected_span"]
        if got_b != sid:
            fails.append(("B", tid[:8], sid, got_b))

print(f"checked {checked} (trace,span) pairs x 2 scenarios = {checked*2} runs")
if fails:
    print(f"FAILURES: {len(fails)}")
    for f in fails[:30]:
        print("  ", f)
    sys.exit(1)
else:
    print("ALL PASS")
