# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
src = open(p, encoding="utf-8").read()

rules = [
    ("#### " + chr(0x1F5C2) + " Navigation Tree ",
     "#### " + chr(0x1F5C2) + " " + chr(0x5BFC) + chr(0x822A) + chr(0x6811) + " "),
    (chr(0x23F1) + "  Flow state ({len(events)} event(s))",
     chr(0x23F1) + "  " + chr(0x6D41) + chr(0x7A0B) + chr(0x4E8B) + chr(0x4EF6) + chr(0xFF08) + "{len(events)} " + chr(0x6761) + chr(0xFF09)),
    ("Click a node in the tree to inspect it.",
     chr(0x8BF7) + chr(0x5728) + chr(0x5DE6) + chr(0x4FA7) + chr(0x6811) + chr(0x4E2D) + chr(0x9009) + chr(0x4E2D) + chr(0x4E00) + chr(0x4E2A) + chr(0x8282) + chr(0x70B9) + chr(0x67E5) + chr(0x770B) + chr(0x8BE6) + chr(0x60C5) + chr(0x3002)),
    ('rows.append(("Tags", ", ".join(str(t) for t in tags)))',
     'rows.append(("' + chr(0x6807) + chr(0x7B7E) + '", ", ".join(str(t) for t in tags)))'),
    ('<div class="k">In / Out</div>',
     '<div class="k">' + chr(0x8F93) + chr(0x5165) + ' / ' + chr(0x8F93) + chr(0x51FA) + '</div>'),
    (chr(0x1F4B0) + " estimated cost (this span): **" + chr(0x24) + "{cost:.4f}**",
     chr(0x1F4B0) + " " + chr(0x672C) + " span " + chr(0x4F30) + chr(0x8BA1) + chr(0x6210) + chr(0x672C) + chr(0xFF1A) + "**" + chr(0x24) + "{cost:.4f}**"),
]

total = 0
for old, new in rules:
    c = src.count(old)
    if c:
        src = src.replace(old, new)
        total += c
        print("HIT n=" + str(c))
    else:
        print("miss (" + old[:50] + ")")
open(p, "w", encoding="utf-8", newline="\n").write(src)
print("Total substitutions: " + str(total))