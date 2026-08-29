# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer\normalize.py"
content = open(p, encoding="utf-8").read()

# 1) Insert _reconstruct_indexed_list BEFORE the "# canon() - the workhorse" header.
anchor = "# canon() - the workhorse"
assert anchor in content, "anchor not found"

helper = (
    "def _reconstruct_indexed_list(attrs, prefix):\n"
    "    \"\"\"Reconstruct a list from flat dotted keys like '<prefix>.0.message.role'.\n"
    "    The OpenInference JSONL exporter flattens list items by integer index.\n"
    "    Returns None if no keys with the given prefix are found.\n"
    "    \"\"\"\n"
    "    if not isinstance(attrs, dict):\n"
    "        return None\n"
    "    prefix_dot = prefix + '.'\n"
    "    items = {}\n"
    "    for k, v in attrs.items():\n"
    "        if not isinstance(k, str) or not k.startswith(prefix_dot):\n"
    "            continue\n"
    "        rest = k[len(prefix_dot):]\n"
    "        parts = rest.split('.', 1)\n"
    "        if not parts or not parts[0].isdigit():\n"
    "            continue\n"
    "        idx = int(parts[0])\n"
    "        sub_path = parts[1] if len(parts) > 1 else ''\n"
    "        items.setdefault(idx, {})[sub_path] = v\n"
    "    if not items:\n"
    "        return None\n"
    "    max_idx = max(items.keys())\n"
    "    out = []\n"
    "    for i in range(max_idx + 1):\n"
    "        flat_for_i = items.get(i, {})\n"
    "        nested = {}\n"
    "        for sub_key, sub_val in flat_for_i.items():\n"
    "            if not sub_key:\n"
    "                nested['_value'] = sub_val\n"
    "                continue\n"
    "            segs = sub_key.split('.')\n"
    "            cur = nested\n"
    "            for s in segs[:-1]:\n"
    "                if not isinstance(cur, dict):\n"
    "                    break\n"
    "                nxt = cur.get(s)\n"
    "                if nxt is None or not isinstance(nxt, dict):\n"
    "                    nxt = {}\n"
    "                    cur[s] = nxt\n"
    "                cur = nxt\n"
    "            cur[segs[-1]] = sub_val\n"
    "        out.append(nested)\n"
    "    return out\n"
    "\n"
    "\n"
)

content = content.replace(anchor, helper + anchor, 1)
print("Helper inserted")

# 2) Insert the flat-indexed reconstruction section in canon()
canon_anchor = "    # 2) LangChain fallback: token counts inside the JSON output.value"
assert canon_anchor in content, "canon anchor not found"

new_section = (
    "    # 3) Flat-indexed reconstruction: OpenInference exporter writes\n"
    "    #    \"llm.input_messages.0.message.role\" instead of nested lists.\n"
    "    if key.startswith('messages.'):\n"
    "        side = key.split('.', 1)[1]\n"
    "        for prefix in (f'llm.{side}_messages', f'gen_ai.{side}.messages'):\n"
    "            lst = _reconstruct_indexed_list(attrs, prefix)\n"
    "            if lst:\n"
    "                return lst\n"
    "\n"
)

content = content.replace(canon_anchor, new_section + canon_anchor, 1)
print("canon section 3 added")

open(p, "w", encoding="utf-8", newline="\n").write(content)
print("Bytes:", len(content.encode("utf-8")))