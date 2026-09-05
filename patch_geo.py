path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Dynamic viewState based on cells
old_state = """  const [viewState, setViewState] = useState({
    longitude: 88.5122,
    latitude: 27.3314, // North Sikkim Center
    zoom: 11,
    pitch: 0,
    bearing: 0
  });"""

new_state = """  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;
  const defaultCenter = isNepal ? { lon: 85.3, lat: 28.1, zoom: 9 } : { lon: 88.5122, lat: 27.3314, zoom: 11 };

  const [viewState, setViewState] = useState({
    longitude: defaultCenter.lon,
    latitude: defaultCenter.lat,
    zoom: defaultCenter.zoom,
    pitch: 0,
    bearing: 0
  });
  
  // Re-center map if region changes
  useEffect(() => {
    setViewState(prev => ({
      ...prev,
      longitude: defaultCenter.lon,
      latitude: defaultCenter.lat,
      zoom: defaultCenter.zoom
    }));
  }, [isNepal]);
"""
content = content.replace(old_state, new_state)

old_fallback = """      } else {
        mapRef.current.flyTo({
          center: [88.5122, 27.3314],
          zoom: 11,
          pitch: 0,
          bearing: 0,
          duration: 2000,
        });
      }"""
new_fallback = """      } else {
        mapRef.current.flyTo({
          center: [defaultCenter.lon, defaultCenter.lat],
          zoom: defaultCenter.zoom,
          pitch: 0,
          bearing: 0,
          duration: 2000,
        });
      }"""
content = content.replace(old_fallback, new_fallback)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("GeospatialViewer fixed for Nepal coordinates")
