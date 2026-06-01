import re
with open('app/routes/academic.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace("\\'", "'")
with open('app/routes/academic.py', 'w', encoding='utf-8') as f:
    f.write(c)
