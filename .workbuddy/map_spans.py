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

def latest(tid): return max((int(s.get('start_time',0)) for s in by_trace[tid]), default=0)
trace_ids=sorted(by_trace.keys(), key=lambda t:(len(by_trace[t]), latest(t)), reverse=True)
print('trace order (first 8):')
for t in trace_ids[:8]:
    print(' ', t[:8], 'spans=', len(by_trace[t]), 'latest=', latest(t))

for tid in [t for t in trace_ids if t.startswith('03dfbce2')]:
    print('=== trace', tid)
    for s in sorted(by_trace[tid], key=lambda s:int(s.get('start_time',0))):
        attrs=s.get('attributes') or {}
        kind=attrs.get('openinference.span.kind') or s.get('kind')
        print(f"  span_id={s['span_id']} name={s.get('name')!r} kind={kind} parent={s.get('parent_span_id')}")
