# -*- coding: utf-8 -*-
# Unambiguous check: count exact ASCII substrings in the working file.
p = r'D:\my-projects\agent-monitor\viewer.py'
text = open(p, 'rb').read().decode('utf-8', errors='replace')
checks = [
    ('A', 'if(m)sid=m;'),
    ('B', 'if(m)sid=m[0];'),
    ('C', 'var sid=m.slice(2)'),
    ('D', 'var sid=m[0].slice(2)'),
    ('E', 'window.CURRENT_TRACE='),
    ('F', 'searchParams.set("trace"'),
]
for tag, s in checks:
    print(tag, text.count(s), repr(s))
