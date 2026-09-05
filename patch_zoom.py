path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_fly = """      mapRef.current.flyTo({
        center: [cell.centroid_lon, cell.centroid_lat],
        zoom: 12.5,
        pitch: 75,
        bearing: 25,"""

new_fly = """      mapRef.current.flyTo({
        center: [cell.centroid_lon, cell.centroid_lat],
        zoom: isNepal ? 10.5 : 12.5,
        pitch: 75,
        bearing: 25,"""

content = content.replace(old_fly, new_fly)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed zoom level for Nepal")
