geo_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(geo_path, "r", encoding="utf-8") as f:
    geo = f.read()

import re
geo = re.sub(r'{\s*selectedCell\s*&&\s*\(\s*\)\s*}', '', geo)

with open(geo_path, "w", encoding="utf-8") as f:
    f.write(geo)
print("Fixed empty braces")
