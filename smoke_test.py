"""Smoke test for the viewer/* package.

Run with:
    cd D:\my-projects\agent-monitor
    python smoke_test.py

This exercises every public function against the real ``latest_traces.jsonl``
so you can confirm naming/visibility/field normalization without launching
Streamlit.
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter

# Make sure we run from the project root (this file lives there too)
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from viewer.canonical  import SPAN_KINDS, FIELD_ALIASES
from viewer.normalize  import canon, friendly_name, span_kind, to_messages
from viewer.visibility import is_span_visible, filter_visible_attrs

DEFAULT_TRACE_FILE = os.path.join(project_root, "latest_traces.jsonl")
ALT_TRACE_FILE     = r"D:\agent\complex-agent-langchain\latest_traces.jsonl"

def _load(path):
    if not os.path.isfile(path):
        return None
    out = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def main() -> int:
    for path in (DEFAULT_TRACE_FILE, ALT_TRACE_FILE):
        if os.path.isfile(path):
            trace_file = path
            break
    else:
        print("No latest_traces.jsonl found.")
        return 1

    print(f"Reading: {trace_file}\n")
    spans = _load(trace_file)
    print(f"Loaded {len(spans)} spans\n")

    # 1. canonical / normalize basics
    print("=== Span kinds (unique) ===")
    counts = Counter(span_kind(s.get("attributes") or {}) for s in spans)
    for k, c in counts.most_common():
        info = SPAN_KINDS.get(k, SPAN_KINDS["UNKNOWN"])
        print(f"  {info[0]} {k:12}  label='{info[2]}'  count={c}")

    # 2. friendly name translation
    print("\n=== Friendly-name translations ===")
    seen_pairs = set()
    for s in spans:
        attrs = s.get("attributes") or {}
        kind = span_kind(attrs)
        raw_name = s.get("name", "")
        if (raw_name, kind) in seen_pairs:
            continue
        seen_pairs.add((raw_name, kind))
        disp, vis = friendly_name(raw_name, kind)
        marker = "OK  " if vis else "HIDE"
        print(f"  [{marker}] {raw_name:40s} ({kind:8s}) -> {disp}")

    # 3. canonical-key reads (tokens.)
    print("\n=== Token extraction (sample spans) ===")
    sample = [s for s in spans if span_kind(s.get("attributes") or {}) == "LLM"][:5]
    for s in sample:
        attrs = s.get("attributes") or {}
        print(f"  span name = {s.get('name','?'):18}  "
              f"in={canon(attrs, 'tokens.input')!s:>8} "
              f"out={canon(attrs, 'tokens.output')!s:>8} "
              f"total={canon(attrs, 'tokens.total')!s:>8} "
              f"cache={canon(attrs, 'tokens.cache_read')!s:>8} "
              f"reasoning={canon(attrs, 'tokens.reasoning')!s:>8}")

    # 4. messages parsing
    print("\n=== Message parsing (LLM spans) ===")
    for s in [x for x in spans if span_kind(x.get("attributes") or {}) == "LLM"][:2]:
        attrs = s.get("attributes") or {}
        mi = to_messages(canon(attrs, "messages.input"))
        mo = to_messages(canon(attrs, "messages.output"))
        print(f"  span {s.get('span_id','?')[:8]}:  in={len(mi)} msgs  out={len(mo)} msgs")
        for m in mi:
            tcs = [tc.get("name") for tc in m.get("tool_calls") or []]
            content_preview = (m.get("content") or "")[:60].replace("\n", " ")
            print(f"     [{m.get('role')}]  '{content_preview}\u2026'  tool_calls={tcs}")

    # 5. visibility filter
    print("\n=== Visibility filter (hide_plumbing=True) ===")
    visible_total = sum(1 for s in spans if is_span_visible(s))
    hidden_total  = sum(1 for s in spans if not is_span_visible(s))
    visible_total2= sum(1 for s in spans if is_span_visible(s, show_all=True))
    print(f"  default: visible={visible_total}  hidden={hidden_total}")
    print(f"  show_all=True: visible={visible_total2} (everything)")

    print("\nAll smoke checks completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
