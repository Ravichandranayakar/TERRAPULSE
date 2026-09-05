import re

with open('apps/terrapulse/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

bad = '            </div>\n          <div className="hidden sm:flex items-center gap-5">'
good = '            </div>\n          </div>\n          <div className="hidden sm:flex items-center gap-5">'

content = content.replace(bad, good)

with open('apps/terrapulse/frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
