import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()
lines = content.splitlines()

# Find _render_flowchart_mode(...) call block and unindent by 4 spaces
for i, l in enumerate(lines):
    if "_render_flowchart_mode(" in l and l.startswith("    _render_flowchart_mode"):
        # Find block end: until closing ")" at 4-space indent
        j = i
        while j < len(lines):
            if lines[j].startswith("    )") and "_render_flowchart_mode" not in lines[j]:
                # The closing ")" 
                # Find start of close: "    )" alone on line
                pass
            j += 1
        # Simpler: unindent lines i..j
        # Find where block ends - look for "    )" line (4 spaces + close paren)
        for k in range(i, len(lines)):
            if lines[k].strip() == ")" and lines[k].startswith("    "):
                block_end = k
                break
        # Unindent lines i..block_end
        for k in range(i, block_end + 1):
            if lines[k].startswith("    "):
                lines[k] = lines[k][4:]
        print(f"Unindented block L{i+1}-L{block_end+1}")
        break

open(p, "w", encoding="utf-8", newline="\n").write(chr(10).join(lines) + chr(10))