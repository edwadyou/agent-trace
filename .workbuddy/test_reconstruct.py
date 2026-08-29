# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\my-projects\agent-monitor")
from viewer.normalize import canon

spans = []
with open(r"D:\agent\complex-agent-langchain\latest_traces.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: spans.append(json.loads(line))
        except: pass

llm = next(s for s in spans if (s.get("attributes") or {}).get("openinference.span.kind") == "LLM")
attrs = llm["attributes"]

msgs = canon(attrs, "messages.input")
print("messages.input type:", type(msgs).__name__)
print("count:", len(msgs) if msgs else 0)
if msgs:
    print("first:", {k: (v[:60] + "...") if isinstance(v, str) and len(v) > 60 else v for k, v in msgs[0].items()})
    print("roles:", [m.get("message", {}).get("role") for m in msgs])
msgs_out = canon(attrs, "messages.output")
print("messages.output count:", len(msgs_out) if msgs_out else 0)
if msgs_out:
    print("out roles:", [m.get("message", {}).get("role") for m in msgs_out])

# Also test that backward compatibility still works for non-indexed flat keys
print()
print("Backward compat: llm.token_count.prompt =", canon(attrs, "tokens.input"))
print("model =", canon(attrs, "model"))