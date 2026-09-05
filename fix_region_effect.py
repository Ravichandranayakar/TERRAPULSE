filepath = r'C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the problem: regionDefaults is computed INSIDE the component each render
# but flyTo fires on EVERY regionState.region change, even on first mount.
# Correct flow:
# 1. Use useRef to track the PREVIOUS region so we only fly when it ACTUALLY changes
# 2. Always reset 3D state when region switches
# 3. Clear selectedCell when switching regions

old_effect = """  // Fly to new region center when mode switches
  React.useEffect(() => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [regionDefaults.longitude, regionDefaults.latitude],
        zoom: regionDefaults.zoom,
        pitch: 0,
        bearing: 0,
        duration: 2000,
      });
    }
  }, [regionState.region]);"""

new_effect = """  // Track previous region to detect ACTUAL changes (not initial mount)
  const prevRegionRef = React.useRef<string>(regionState.region);

  React.useEffect(() => {
    // Only fly if the region actually changed (not on first render)
    if (prevRegionRef.current !== regionState.region) {
      prevRegionRef.current = regionState.region;
      
      // Reset 3D mode and selected cell
      setIs3D(false);
      setSelectedCell(null);
      setSaved2DState(null);
      
      // Compute new defaults based on new region
      const newDefaults = regionState.region === 'nepal_case'
        ? { longitude: 85.275, latitude: 28.075, zoom: 9 }
        : { longitude: 88.5122, latitude: 27.3314, zoom: 9 };

      // Fly to new region after a short delay to allow 3D reset to settle
      setTimeout(() => {
        if (mapRef.current) {
          mapRef.current.flyTo({
            center: [newDefaults.longitude, newDefaults.latitude],
            zoom: newDefaults.zoom,
            pitch: 0,
            bearing: 0,
            duration: 2000,
          });
        }
      }, 100);
    }
  }, [regionState.region]);"""

content = content.replace(old_effect, new_effect)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
