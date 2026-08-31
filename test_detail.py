"""Unit test: verify _render_detail_column updates selected_span when focus is set."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import importlib.util
spec = importlib.util.spec_from_file_location("viewer", r"D:\my-projects\agent-monitor\viewer.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# We can not actually exercise Streamlit widgets without AppTest, but we
# can at least inspect the source of _render_detail_column.
import inspect
src = inspect.getsource(m._render_detail_column)
print("=== _render_detail_column source ===")
print(src)