path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

import re

# Remove the Mock UI block completely
pattern = r"\{/\* MOCK UI FOR CANDIDATE SLOPE SCANNING.*?\{/\* SELECTED CELL DETAILS PANEL \*/\}"
new_content = re.sub(pattern, "{/* SELECTED CELL DETAILS PANEL */}", content, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)
print("Removed Mock UI")
