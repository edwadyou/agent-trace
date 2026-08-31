# -*- coding: utf-8 -*-
"""Precisely fix the two JS bugs in viewer.py's mermaid click handler.

Bug 1:  if(m)sid=m;                  ->  if(m)sid=m[0];      (match ARRAY, not string)
Bug 2:  var sid=m.slice(2)....       ->  var sid=m[0].slice(2)....  (array.slice() -> .replace TypeError)
"""
p = r'D:\my-projects\agent-monitor\viewer.py'
data = open(p, 'rb').read()
text = data.decode('utf-8')

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'[FAIL] {label}: expected 1 occurrence of {old!r}, found {n}')
    return text.replace(old, new)

text = replace_once(text, "if(m)sid=m;", "if(m)sid=m[0];", 'bug1')
text = replace_once(text, "var sid=m.slice(2)", "var sid=m[0].slice(2)", 'bug2')

open(p, 'w', encoding='utf-8', newline='').write(text)
print('OK: both JS bugs fixed')
# verify
data2 = open(p, 'rb').read().decode('utf-8')
print('if(m)sid=m;            count:', data2.count('if(m)sid=m;'))
print('if(m)sid=m[0];         count:', data2.count('if(m)sid=m[0];'))
print('var sid=m.slice(2)     count:', data2.count('var sid=m.slice(2)'))
print('var sid=m[0].slice(2)  count:', data2.count('var sid=m[0].slice(2)'))
