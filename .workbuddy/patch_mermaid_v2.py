import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

# === Fix 1: safe regex - only strip Mermaid syntax chars, keep <> ===
old_safe = '        safe = re.sub(r"[\\[\\](){}<>|`]", " ", full_label).strip()'
new_safe = '        safe = re.sub(r"[\\"\\#;|]", " ", full_label).strip()'
if old_safe in content:
    content = content.replace(old_safe, new_safe, 1)
    print("Fix 1: safe regex updated (preserves <, >)")
else:
    print("Fix 1: safe regex pattern not found")

# === Fix 2: Replace subgraph block with chain-inference logic ===
old_subgraph_block = (
        '    # Group parallel children in subgraphs\n'
        '    for parent_id, kids in children_by_parent.items():\n'
        '        if len(kids) < 2:\n'
        '            continue\n'
        '        # Sort by start time\n'
        '        kids.sort(key=lambda s: int(s.get("start_time", 0)))\n'
        '        # Check if any pair starts within 5ms\n'
        '        starts_k = [int(k.get("start_time", 0)) / 1_000_000 for k in kids]\n'
        '        is_parallel = False\n'
        '        for i in range(len(starts_k) - 1):\n'
        '            if abs(starts_k[i + 1] - starts_k[i]) <= 5:\n'
        '                is_parallel = True\n'
        '                break\n'
        '        if is_parallel:\n'
        '            pnid = _mermaid_safe_id(parent_id)\n'
        '            out.append(f"    subgraph SG_{pnid}[\\"\\u5e76\\u884c\\u5206\\u652f\\"]")\n'
        '            out.append("    direction LR")\n'
        '            for k in kids:\n'
        '                out.append(f"        {_mermaid_safe_id(k[\'span_id\'])}")\n'
        '            out.append("    end")\n'
    )
new_subgraph_block = (
        '    # Infer chain vs parallel from time-overlap:\n'
        '    # - chain (sequential):  every consecutive pair is non-overlapping\n'
        '    #   (next.start >= prev.end) -- sibling-to-sibling edges draw a left-to-right chain\n'
        '    # - parallel:           at least one pair overlaps in time\n'
        '    #   -- wrap in subgraph labelled \u5e76\u884c\u5206\u652f\n'
        '    for parent_id, kids in children_by_parent.items():\n'
        '        if len(kids) < 2:\n'
        '            continue\n'
        '        sorted_kids = sorted(kids, key=lambda s: int(s.get("start_time", 0)))\n'
        '        n_kids = len(sorted_kids)\n'
        '        all_sequential = True\n'
        '        for i in range(n_kids - 1):\n'
        '            prev_end = int(sorted_kids[i].get("end_time", 0))\n'
        '            next_start = int(sorted_kids[i + 1].get("start_time", 0))\n'
        '            if next_start < prev_end:\n'
        '                all_sequential = False\n'
        '                break\n'
        '        pnid = _mermaid_safe_id(parent_id)\n'
        '        if all_sequential:\n'
        '            # Chain: parent connects to first child only; siblings chain in time\n'
        '            first_id = _mermaid_safe_id(sorted_kids[0]["span_id"])\n'
        '            out.append(f"    {pnid} --> {first_id}")\n'
        '            for i in range(n_kids - 1):\n'
        '                a = _mermaid_safe_id(sorted_kids[i]["span_id"])\n'
        '                b = _mermaid_safe_id(sorted_kids[i + 1]["span_id"])\n'
        '                out.append(f"    {a} --> {b}")\n'
        '        else:\n'
        '            # Parallel: wrap in subgraph; all children fan out from parent\n'
        '            out.append(\'    subgraph SG_\' + pnid + \'["\\u5e76\\u884c\\u5206\\u652f"]\')\n'
        '            out.append("    direction LR")\n'
        '            for k in sorted_kids:\n'
        '                out.append(f"        {_mermaid_safe_id(k[\'span_id\'])}")\n'
        '            out.append("    end")\n'
        '            for k in sorted_kids:\n'
        '                out.append(f"    {pnid} --> {_mermaid_safe_id(k[\'span_id\'])}")\n'
    )
if old_subgraph_block in content:
    content = content.replace(old_subgraph_block, new_subgraph_block, 1)
    print("Fix 2: subgraph block replaced with all_sequential inference")
else:
    print("Fix 2: subgraph block pattern not found")
    # Debug
    idx = content.find('    # Group parallel children in subgraphs')
    print('debug: at idx', idx, repr(content[idx:idx+800]) if idx > 0 else 'not found')

open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)
print("Bytes:", len(content.encode("utf-8")))