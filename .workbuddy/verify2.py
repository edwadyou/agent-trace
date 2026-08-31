import hashlib
p = r'D:\my-projects\agent-monitor\viewer.py'
data = open(p, 'rb').read()
print('file size:', len(data))
print('md5:', hashlib.md5(data).hexdigest())
text = data.decode('utf-8')
print('occurrences of "if(m)sid=m;" :', text.count('if(m)sid=m;'))
print('occurrences of "if(m)sid=m[0];":', text.count('if(m)sid=m[0];'))
print('occurrences of "var sid=m.slice(2)":', text.count('var sid=m.slice(2)'))
print('occurrences of "var sid=m[0].slice(2)":', text.count('var sid=m[0].slice(2)'))
print('occurrences of CURRENT_TRACE:', text.count('CURRENT_TRACE'))
# print the exact region around each occurrence
for marker in ['if(m)sid', 'var sid=m']:
    idx = text.find(marker)
    if idx >= 0:
        print('\n--- context for', marker, '---')
        print(repr(text[idx-40:idx+60]))
