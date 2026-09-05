path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\App.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# FIX 1: Remove the forced setUseMapLibre(true) when clicking in 2D map.
# Clicking a circle in 2D should just select it - not jump to 3D.
old_cell_select = """                        onCellSelect={(id) => {
                          setSelectedCellId(id);
                          setUseMapLibre(true);
                        }}"""
new_cell_select = """                        onCellSelect={(id) => {
                          setSelectedCellId(id);
                        }}"""
content = content.replace(old_cell_select, new_cell_select)

# FIX 2: Also make sure regionState change resets useMapLibre to false
# We need to find where regionState region changes and add a reset
old_fetch_all = """  const fetchAll = useCallback(async () => {
    try {
      const [geo, status, activeWarnings] = await Promise.all([
        rpcCall({ func: 'get_geo_data', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_latest_status', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } }),
      ]);
      setGeoData(geo);
      setForecastData(null); // Clear forecast when region changes so it re-fetches"""
new_fetch_all = """  const fetchAll = useCallback(async () => {
    try {
      const [geo, status, activeWarnings] = await Promise.all([
        rpcCall({ func: 'get_geo_data', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_latest_status', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } }),
      ]);
      setGeoData(geo);
      setForecastData(null); // Clear forecast when region changes so it re-fetches
      setSelectedCellId(null); // Clear selected cell when region changes
      setUseMapLibre(false); // Always reset to 2D when switching region"""
content = content.replace(old_fetch_all, new_fetch_all)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed App.tsx region switching and cell selection logic")
