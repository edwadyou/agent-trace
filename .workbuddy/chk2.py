# -*- coding: utf-8 -*-
# Bulletproof check using chr() for brackets to avoid any display mangling.
p = r'D:\my-projects\agent-monitor\viewer.py'
text = open(p, 'rb').read().decode('utf-8', errors='replace')
LB = chr(91)   # [
RB = chr(93)   # ]
fix1 = 'if(m)sid=m' + LB + '0' + RB + ';'
bug1 = 'if(m)sid=m;'
fix2 = 'var sid=m' + LB + '0' + RB + '.slice(2)'
bug2 = 'var sid=m.slice(2)'
print('fix1 count =', text.count(fix1))
print('bug1 count =', text.count(bug1))
print('fix2 count =', text.count(fix2))
print('bug2 count =', text.count(bug2))
print('trace   count =', text.count('searchParams.set("trace"'))
