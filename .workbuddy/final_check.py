# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

import py_compile
files = ['viewer.py', 'viewer/canonical.py', 'viewer/naming/langchain.py']
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print('OK  ' + f)
    except py_compile.PyCompileError as e:
        print('FAIL  ' + f + ': ' + str(e))

print()
print('Import check:')
from viewer.canonical import SPAN_KINDS
print('  OK  viewer.canonical')
expected_labels = [
    "\u5927\u6a21\u578b\u8c03\u7528",
    "\u94fe\u8def\u6b65\u9aa4",
    "\u5de5\u5177\u8c03\u7528",
    "\u667a\u80fd\u4f53",
    "\u68c0\u7d22",
    "\u5411\u91cf\u5316",
    "\u91cd\u6392\u5e8f",
    "\u586b\u5145\u63d0\u793a\u8bcd",
    "\u89e3\u6790\u54cd\u5e94",
    "\u8bc4\u4f30",
    "\u5b89\u5168\u68c0\u67e5",
    "\u672a\u77e5",
]
actual_labels = {info[2] for info in SPAN_KINDS.values()}
miss = [l for l in expected_labels if l not in actual_labels]
print('  Chinese labels present:', not miss)
if miss:
    print('  Missing:', miss)

print()
print('Naming translation check:')
from viewer.naming import friendly_name
cases = [
    ("ChatOpenAI", "LLM", "\u5927\u6a21\u578b\u8c03\u7528\uff08OpenAI\uff09"),
    ("ChatPromptTemplate", "PROMPT", "\u586b\u5145\u5bf9\u8bdd\u63d0\u793a\u8bcd"),
    ("RunnableSequence", "CHAIN", "\u94fe\u8def\u6b65\u9aa4"),
    ("RunnableParallel<web_search,knowledge_base>", "CHAIN", "\u591a\u4efb\u52a1\u5e76\u884c\uff1aweb_search, knowledge_base"),
    ("PydanticOutputParser", "CHAIN", "\u7ed3\u6784\u5316\u6821\u9a8c"),
    ("AgentExecutor", "AGENT", "\u667a\u80fd\u4f53\u6267\u884c"),
    ("VectorStoreRetriever", "RETRIEVER", "\u5411\u91cf\u5e93\u68c0\u7d22"),
    ("PlanAndExecute", "AGENT", "\u8ba1\u5212\u5e76\u6267\u884c"),
]
fail = 0
for name, kind, expected in cases:
    actual, _ = friendly_name(name, kind)
    ok = actual == expected
    mark = "OK" if ok else "FAIL"
    print("  " + mark + "  " + name[:35].ljust(35) + " (" + kind.ljust(8) + ") -> " + actual)
    if not ok:
        print("         expected:", expected)
        fail += 1
print()
print("Failures:", fail)

print()
print("viewer.py AST check:")
import ast
with open("viewer.py", encoding="utf-8") as f:
    tree = ast.parse(f.read())
funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
print("  total functions:", len(funcs))
for n in ["_trace_label", "_fmt_trace_option", "_build_mermaid", "_render_mermaid_html",
          "_render_flowchart_mode", "_render_run_tab", "_render_msg", "_render_tree"]:
    present = n in funcs
    print("  " + ("OK" if present else "MISSING") + "  " + n)