geo_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(geo_path, "r", encoding="utf-8") as f:
    geo = f.read()

old_func = """export default function GeospatialViewer({ 
  cells = [], 
  historicalEvents = [],
  nh10Route = [],
  onCellClick,
  initialSelectedCellId
}: {"""
new_func = """export default function GeospatialViewer({ 
  cells = [], 
  historicalEvents = [],
  nh10Route = [],
  routeSafety,
  onCellClick,
  initialSelectedCellId
}: {"""

geo = geo.replace(old_func, new_func)

with open(geo_path, "w", encoding="utf-8") as f:
    f.write(geo)
print("Destructuring fixed!")
