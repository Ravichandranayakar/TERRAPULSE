with open('apps/terrapulse/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("fetch(http://localhost:5000/api/forecast?region_id=)", "fetch(`http://localhost:5000/api/forecast?region_id=${regionState.region}`)")

with open('apps/terrapulse/frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
