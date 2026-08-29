import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

# 1) Add _handled_parents = set() before the chain/parallel block
old_marker = "    # Infer chain vs parallel from time-overlap:"
new_marker = (
    "    # Track parents whose edges are emitted by the chain/parallel block below,\n"
    "    # so the main edge loop skips them.\n"
    "    _handled_parents = set()\n"
    "\n"
    "    # Infer chain vs parallel from time-overlap:"
)
if old_marker in content:
    content = content.replace(old_marker, new_marker, 1)
    print("_handled_parents initialized")
else:
    print("marker not found")

# 2) In chain branch: add pnid to _handled_parents
old_chain = (
    "        if all_sequential:\n"
    "            # Chain: parent connects to first child only; siblings chain in time\n"
    "            first_id = _mermaid_safe_id(sorted_kids[0][\"span_id\"])\n"
    "            out.append(f\"    {pnid} --> {first_id}\")\n"
)
new_chain = (
    "        if all_sequential:\n"
    "            # Chain: parent connects to first child only; siblings chain in time\n"
    "            _handled_parents.add(parent_id)\n"
    "            first_id = _mermaid_safe_id(sorted_kids[0][\"span_id\"])\n"
    "            out.append(f\"    {pnid} --> {first_id}\")\n"
)
if old_chain in content:
    content = content.replace(old_chain, new_chain, 1)
    print("Chain branch updated")
else:
    print("chain branch not found")

# 3) In parallel branch: add pnid to _handled_parents
old_parallel = (
    "        else:\n"
    "            # Parallel: wrap in subgraph; all children fan out from parent\n"
    "            out.append(\'    subgraph SG_\' + pnid + \'[\"\u5e76\u884c\u5206\u652f\"]\')\n"
)
new_parallel = (
    "        else:\n"
    "            # Parallel: wrap in subgraph; all children fan out from parent\n"
    "            _handled_parents.add(parent_id)\n"
    "            out.append(\'    subgraph SG_\' + pnid + \'[\"\u5e76\u884c\u5206\u652f\"]\')\n"
)
if old_parallel in content:
    content = content.replace(old_parallel, new_parallel, 1)
    print("Parallel branch updated")
else:
    print("parallel branch not found")

open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)