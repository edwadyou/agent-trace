# -*- coding: utf-8 -*-
"""Unit-test _build_mermaid against real traces."""
import sys, json, importlib.util
sys.stdout.reconfigure(encoding="utf-8")

# Load just the module (skip streamlit dep)
src_text = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
# Find _build_mermaid and dependencies
import re
# Extract _mermaid_safe_id and _mermaid_label bodies
m_safe = re.search(r"def _mermaid_safe_id\(sid\):.*?(?=\n\ndef |\nclass |\n# )", src_text, re.DOTALL)
m_lab = re.search(r"def _mermaid_label\(span\):.*?(?=\n\ndef |\nclass |\n# )", src_text, re.DOTALL)
m_build = re.search(r"def _build_mermaid\(spans, \*, focus=None, hops=2\):.*?(?=\n\n\ndef )", src_text, re.DOTALL)
# Build a tiny module with these + helpers
helpers_src = '''
import re
SPAN_KINDS = {
    "LLM":       ("\\U0001F916", "blue",   "\u5927\u6a21\u578b\u8c03\u7528"),
    "CHAIN":     ("\\U0001F517", "green",  "\u94fe\u8def\u6b65\u9aa4"),
    "TOOL":      ("\\U0001F527", "orange", "\u5de5\u5177\u8c03\u7528"),
    "AGENT":     ("\\U0001F9E0", "yellow", "\u667a\u80fd\u4f53"),
    "RETRIEVER": ("\\U0001F4DA", "purple", "\u68c0\u7d22"),
    "EMBEDDING": ("\\U0001F4D0", "cyan",   "\u5411\u91cf\u5316"),
    "RERANKER":  ("\\U0001F3AF", "violet", "\u91cd\u6392\u5e8f"),
    "PROMPT":    ("\\U0001F4DD", "olive",  "\u586b\u5145\u63d0\u793a\u8bcd"),
    "PARSER":    ("\\U0001F50D", "gray",   "\u89e3\u6790\u54cd\u5e94"),
    "EVALUATOR": ("\\u2696\\uFE0F",  "tan",   "\u8bc4\u4f30"),
    "GUARDRAIL": ("\\U0001F6E1\\uFE0F", "red",    "\u5b89\u5168\u68c0\u67e5"),
    "UNKNOWN":   ("\\u2754",   "gray",   "\u672a\u77e5"),
}

def span_kind(attrs):
    if not isinstance(attrs, dict): return "UNKNOWN"
    v = attrs.get("openinference.span.kind") or attrs.get("kind")
    if v is None: return "UNKNOWN"
    return str(v).upper()

def canon(attrs, key, default=None):
    return default

def _span_display_name(span):
    return span.get("name", "?")

def _format_duration_ms(ms):
    if ms is None: return "-"
    if ms >= 60000: return f"{ms/60000:.1f}m"
    if ms >= 1000: return f"{ms/1000:.2f}s"
    return f"{ms:.0f}ms"

''' + m_safe.group() + "\n\n" + m_lab.group() + "\n\n_MERMAID_MAX_NODES = 80\n_NODE_LABEL_MAX_CHARS = 60\n" + m_build.group()
# Write to temp module and execute
open(r"D:\my-projects\agent-monitor\.workbuddy\_build_test.py", "w", encoding="utf-8").write(helpers_src)
import importlib.util
spec = importlib.util.spec_from_file_location("build_test", r"D:\my-projects\agent-monitor\.workbuddy\_build_test.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Load real traces
spans = []
with open(r"D:\agent\complex-agent-langchain\latest_traces.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: spans.append(json.loads(line))
        except: pass
from collections import defaultdict
by_tid = defaultdict(list)
for s in spans:
    tid = s.get("trace_id")
    if tid: by_tid[tid].append(s)

for trace_idx, (tid, t_spans) in enumerate(by_tid.items()):
    if trace_idx >= 3: break
    out = mod._build_mermaid(t_spans)
    print(f"\n========== Trace {trace_idx}: tid={tid[:8]}... ({len(t_spans)} spans) ==========")
    # Show node labels and edges
    for line in out.split("\n"):
        if line.strip():
            print(line)