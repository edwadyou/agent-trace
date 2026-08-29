import re
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    s = f.read()
# Find the docstring block that contains the English examples
# It is a multiline """...""" inside the _trace_label function near line 880
# Just replace the examples block line by line to avoid the just-word issue
L = [
    ("RunnableParallel<tools...>  -> " + chr(0x22) + "Multi-task parallel (n)" + chr(0x22),
     "RunnableParallel<tools...>  -> " + chr(0x22) + chr(0x591A) + chr(0x4EFB) + chr(0x52A1) + chr(0x5E76) + chr(0x884C) + chr(0xFF08) + "n" + chr(0xFF09) + chr(0x22)),
    (chr(0x22) + "Tool agent" + chr(0x22),
     chr(0x22) + chr(0x5DE5) + chr(0x5177) + chr(0x578B) + chr(0x667A) + chr(0x80FD) + chr(0x4F53) + chr(0x22)),
    (chr(0x22) + "Retrieval chain" + chr(0x22),
     chr(0x22) + chr(0x68C0) + chr(0x7D22) + chr(0x94FE) + chr(0x22)),
    (chr(0x22) + "LLM chain" + chr(0x22),
     chr(0x22) + "LLM " + chr(0x8C03) + chr(0x7528) + chr(0x94FE) + chr(0x22)),
    (chr(0x22) + "LLM call" + chr(0x22),
     chr(0x22) + chr(0x5927) + chr(0x6A21) + chr(0x578B) + chr(0x8C03) + chr(0x7528) + chr(0x22)),
]
for old, new in L:
    n = s.count(old)
    if n:
        s = s.replace(old, new, 1)
        print("  Replaced:", old[:30])
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("Done")
