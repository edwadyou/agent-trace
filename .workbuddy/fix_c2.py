# -*- coding: utf-8 -*-
"""Phase C: fix click + remove expander."""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# C1+C2: use regex to find and update focusSpan block (only the first occurrence is JS function)
# Pattern: window.parent.location.href appears twice (in focusSpan + in DOM delegation)
# We replace BOTH with the robust try/catch version

# Find all occurrences of "var url = new URL(window.parent.location.href);"
# Each is followed by a searchParams.set("focus", ...) and window.parent.location.href = url.toString();

# Use a more flexible regex: capture up to the next window.parent.location.href
pat = re.compile(
    r"(var url = new URL\(window\.parent\.location\.href\);\s*\n\s*url\.searchParams\.set\([\"']focus[\"'], spanId\);\s*\n\s*)window\.parent\.location\.href = url\.toString\(\);"
)
m = pat.search(content)
if m:
    replacement = (
        m.group(1)
        + "try { window.top.location.href = url.toString(); }\n"
        + "        catch (e1) { try { window.parent.location.href = url.toString(); } catch (e2) { window.location.href = url.toString(); } }"
    )
    content = content[:m.start()] + replacement + content[m.end():]
    print("C1+C2: first occurrence (focusSpan function) updated")
else:
    print("C1+C2: first pattern not found")

# Second occurrence (DOM delegation)
m2 = pat.search(content)
if m2:
    replacement2 = (
        m2.group(1)
        + "try { window.top.location.href = url.toString(); }\n"
        + "          catch (e1) { try { window.parent.location.href = url.toString(); } catch (e2) { window.location.href = url.toString(); } }"
    )
    content = content[:m2.start()] + replacement2 + content[m2.end():]
    print("C2: second occurrence (DOM delegation) updated")
else:
    print("C2: second pattern not found")

# Verify no more window.parent.location.href
remaining = content.count("window.parent.location.href")
print(f"Remaining window.parent.location.href occurrences: {remaining}")
# Verify window.top.location.href
print(f"window.top.location.href occurrences: {content.count('window.top.location.href')}")

# C3: remove the manual focus expander
# Search for the expander block by its anchor
expander_anchor = "expanded=False,"
# Find the expander that contains the manual_focus_pick selectbox
manual_idx = content.find('"manual_focus_pick"')
if manual_idx > 0:
    # Walk backwards to find the with st.expander( that opens this block
    # Walk forwards to find the matching close
    # Easier: find the multi-line block by regex
    pat2 = re.compile(
        r"    with st\.expander\(\s*\n"
        r"        \"\\u5982\\u679c\\u70b9\\u51fb\\u65e0\\u6548[^)]*?,\s*\n"
        r"        expanded=False,\s*\n"
        r"    \):.*?st\.button\(\"\\u805a\\u7126\\u5230\\u8be5 span\".*?_jump_to_span\(target_id\)\s*\n"
    )
    m3 = pat2.search(content)
    if m3:
        content = content[:m3.start()] + content[m3.end():]
        print("C3: manual focus expander removed")
    else:
        print("C3: regex didn't match; trying simpler deletion")
        # Simpler: delete from "    with st.expander(" matching closest before manual_focus_pick
        # Find the expander start
        exp_start = content.rfind("    with st.expander(", 0, manual_idx)
        if exp_start > 0:
            # Find the matching close by indentation
            # The expander block has 4-space indent for `with` and 8 for body
            # The body closes with `    )` at 4 spaces? Or 8 spaces? Let's scan.
            lines = content[exp_start:].split("\n")
            close_idx = None
            for li, ln in enumerate(lines):
                # Close of the expander with-block is at column 4 (4 spaces then `)`)
                if li > 0 and ln == "    )":
                    close_idx = exp_start + sum(len(l) + 1 for l in lines[:li])
                    break
            if close_idx is None:
                # try 8 spaces
                for li, ln in enumerate(lines):
                    if li > 0 and ln == "        )":
                        close_idx = exp_start + sum(len(l) + 1 for l in lines[:li])
                        break
            if close_idx is not None:
                # Also remove the trailing newline(s)
                # The expander block ends at close_idx + len(")") + 1
                end = close_idx + 2  # past ")" + newline
                if content[end] == "\n":
                    end += 1
                content = content[:exp_start] + content[end:]
                print("C3: expander deleted (fallback method)")
            else:
                print("C3: couldn't find expander close")
else:
    print("C3: manual_focus_pick not found")

open(p, "w", encoding="utf-8", newline="\n").write(content)