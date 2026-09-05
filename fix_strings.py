import re

with open('apps/terrapulse/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the broken breadcrumbs string
content = content.replace("SIH DEMO ?\" NER / INDIA", "SIH DEMO - NER / INDIA")
content = content.replace("REAL-WORLD CASE ?\" NEPAL", "REAL-WORLD CASE - NEPAL")

# Replace the broken button text
content = content.replace("???? SIH DEMO", "SIH DEMO")
content = content.replace("?? REAL-WORLD CASE", "NEPAL (LIVE)")

with open('apps/terrapulse/frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
