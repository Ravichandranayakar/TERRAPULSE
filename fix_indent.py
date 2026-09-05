import re

with open('apps/terrapulse/backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad = '    print("[TERRAPULSE] Initializing database schema...")\n        conn = _get_db()'
good = '    print("[TERRAPULSE] Initializing database schema...")\n    conn = _get_db()'

# Just to be safe if there are random spaces:
content = re.sub(r'print\("\[TERRAPULSE\] Initializing database schema..."\)\n\s+conn = _get_db\(\)', good, content)

with open('apps/terrapulse/backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
