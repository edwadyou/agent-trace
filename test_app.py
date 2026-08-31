"""End-to-end test using Streamlit AppTest to simulate click flow."""
import os
os.environ["TMPDIR"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TEMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TMP"] = r"D:\my-projects\agent-monitor\.workbuddy\tmp_dir"
os.environ["TRACE_FILE"] = r"D:\agent\complex-agent-langchain\latest_traces.jsonl"

import sys
sys.stdout.reconfigure(encoding="utf-8")

from streamlit.testing.v1 import AppTest

# Test 1: with no focus, no selected_span -> first root
at = AppTest.from_file(r"D:\my-projects\agent-monitor\viewer.py")
at.session_state["selected_trace"] = "f203e21d46f339aadaa7057879fc5fbe"
at.run()
print("=== Run 1: no focus ===")
print("selected_span:", at.session_state.get("selected_span"))
print("Exception:", at.exception)

# Test 2: with focus on span A -> selected_span = span A
at2 = AppTest.from_file(r"D:\my-projects\agent-monitor\viewer.py")
at2.session_state["selected_trace"] = "f203e21d46f339aadaa7057879fc5fbe"
at2.query_params["focus"] = "330d087f75e88c46"
at2.run()
print()
print("=== Run 2: focus=330d087f75e88c46 ===")
print("selected_span:", at2.session_state.get("selected_span"))
print("Exception:", at2.exception)

# Test 3: with focus on span B (different) -> selected_span = span B
at3 = AppTest.from_file(r"D:\my-projects\agent-monitor\viewer.py")
at3.session_state["selected_trace"] = "f203e21d46f339aadaa7057879fc5fbe"
at3.query_params["focus"] = "61d3c38b06ef155b"
at3.run()
print()
print("=== Run 3: focus=61d3c38b06ef155b ===")
print("selected_span:", at3.session_state.get("selected_span"))
print("Exception:", at3.exception)