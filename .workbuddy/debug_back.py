# -*- coding: utf-8 -*-
import os
os.environ["TMPDIR"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TEMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TRACE_FILE"] = r"D:\agent\complex-agent-langchain\latest_traces.jsonl"
import sys
sys.stdout.reconfigure(encoding="utf-8")
from streamlit.testing.v1 import AppTest

VIEWER = r"D:\my-projects\agent-monitor\viewer.py"
at = AppTest.from_file(VIEWER)
at.run()
print("1st selected_span:", at.session_state["selected_span"])
try:
    print("1st _url_focus_applied:", at.session_state["_url_focus_applied"])
except Exception as e:
    print("1st _url_focus_applied: not-set")
print("exceptions:", len(list(at.exception)))

at.session_state["selected_span"] = "4a873fd6c65b7379"
at.run()
print("after set selected_span:", at.session_state["selected_span"])
btn = at.button(key="back_to_overview")
print("has back btn:", btn is not None)
btn.click().run()
print("after back selected_span:", at.session_state["selected_span"])
try:
    print("focus in qp:", at.query_params["focus"])
except Exception:
    print("focus in qp: <none>")
try:
    print("_url_focus_applied:", at.session_state["_url_focus_applied"])
except Exception:
    print("_url_focus_applied: not-set")
print("exceptions after:", len(list(at.exception)))
