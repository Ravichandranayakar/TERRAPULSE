path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("useEffect(() => {", "React.useEffect(() => {")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed useEffect reference")
