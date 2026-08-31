import json, sys
sys.stdout.reconfigure(encoding='utf-8')
rows=[]
with open(r'D:\agent\complex-agent-langchain\latest_traces.jsonl', encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if not line: continue
        rows.append(json.loads(line))
from collections import defaultdict
by_trace=defaultdict(list)
for r in rows:
    by_trace[r['trace_id']].append(r)
tid=[t for t in by_trace if t.startswith('89082226')][0]
print('trace', tid)
for s in sorted(by_trace[tid], key=lambda s:int(s.get('start_time',0))):
    attrs=s.get('attributes') or {}
    kind=attrs.get('openinference.span.kind') or s.get('kind')
    print(f"  span_id={s['span_id']} name={s.get('name')!r} kind={kind} parent={s.get('parent_span_id')}")
