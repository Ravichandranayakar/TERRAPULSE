with open('apps/terrapulse/backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('        print("[TERRAPULSE] Initializing database schema...")'):
        lines[i] = '    print("[TERRAPULSE] Initializing database schema...")\n'

with open('apps/terrapulse/backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
