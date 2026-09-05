app_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\App.tsx"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix duplicate nh10Route
bad_snippet = """              nh10Route={nh10Route}
              routeSafety={routeSafety}
                        historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
                        nh10Route={geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}"""
good_snippet = """              routeSafety={routeSafety}
                        historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
                        nh10Route={nh10Route || geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}"""

content = content.replace(bad_snippet, good_snippet)

# Also pass routeSafety to LandslideMap
bad_map = """                        cells={displayCells}
                        nh10Route={geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}"""
good_map = """                        cells={displayCells}
                        routeSafety={routeSafety}
                        nh10Route={nh10Route || geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}"""

content = content.replace(bad_map, good_map)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("App.tsx fixed")
