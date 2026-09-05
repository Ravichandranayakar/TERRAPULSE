path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

zoom_state_code = """  const [zoom, setZoom] = React.useState(1);
  const handleZoomIn = () => setZoom(z => Math.min(z + 0.5, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.5, 1));
"""

comp_start = """  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;"""
content = content.replace(comp_start, zoom_state_code + "\n" + comp_start)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Injected Zoom state")
