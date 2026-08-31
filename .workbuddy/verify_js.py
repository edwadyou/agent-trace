lines = open(r'D:\my-projects\agent-monitor\viewer.py', 'rb').read().split(b'\n')
keys = [b'sid=m', b'slice(2)', b'CURRENT_TRACE', b'focusSpan=function', b'set("trace"', b'indexOf("n_")']
for i, l in enumerate(lines):
    if any(k in l for k in keys):
        print(i + 1, repr(l[:150]))
