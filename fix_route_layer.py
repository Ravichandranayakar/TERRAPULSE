import re

app_path = r'C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\App.tsx'
geo_viewer_path = r'C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx'

# ============================================================
# 1. Fix App.tsx: normalize status response (handles Nepal {cells:[], route_safety:...} 
#    AND old flat array from NER)
#    Also add routeSafety state and nh10Route state
# ============================================================
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add routeSafety state after statusData state
old_state = "  const [statusData, setStatusData] = useState<GeoCell[]>([]);"
new_state = """  const [statusData, setStatusData] = useState<GeoCell[]>([]);
  const [routeSafety, setRouteSafety] = useState<string>('UNKNOWN');
  const [nh10Route, setNh10Route] = useState<any[]>([]);"""
content = content.replace(old_state, new_state)

# Fix fetchAll to normalize Nepal response
old_fetch = """      setGeoData(geo);
      setStatusData(status);
      setWarnings(activeWarnings);"""

new_fetch = """      setGeoData(geo);
      // Normalize: Nepal returns {cells, route_safety, nh10_route}, NER returns flat array
      if (status && Array.isArray(status)) {
        setStatusData(status);
        setRouteSafety('UNKNOWN');
      } else if (status && status.cells) {
        setStatusData(status.cells);
        setRouteSafety(status.route_safety || 'UNKNOWN');
        setNh10Route(status.nh10_route || []);
      }
      setWarnings(activeWarnings);"""

content = content.replace(old_fetch, new_fetch)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("App.tsx: normalized Nepal status response + routeSafety state")

# ============================================================
# 2. Pass nh10Route and routeSafety to GeospatialViewer
# ============================================================
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find GeospatialViewer usage and add props
old_geo_viewer = 'cells={displayCells}'
new_geo_viewer = 'cells={displayCells}\n              nh10Route={nh10Route}\n              routeSafety={routeSafety}'
content = content.replace(old_geo_viewer, new_geo_viewer, 1)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("App.tsx: passed nh10Route and routeSafety to GeospatialViewer")

# ============================================================
# 3. Update GeospatialViewer: add route layer + Route Safety badge
# ============================================================
with open(geo_viewer_path, "r", encoding="utf-8") as f:
    geo_content = f.read()

# Add routeSafety and nh10Route to props
old_props = "  onCellClick?: (cell: GeoCell) => void,\n  initialSelectedCellId?: string | null\n})"
new_props = """  onCellClick?: (cell: GeoCell) => void,
  initialSelectedCellId?: string | null,
  nh10Route?: any[],
  routeSafety?: string,
})"""
geo_content = geo_content.replace(old_props, new_props)

# Add destructuring of nh10Route and routeSafety in the function
old_dest = "  const { state: regionState } = useRegion();"
new_dest = """  const { state: regionState } = useRegion();
  const resolvedRoute = nh10Route && nh10Route.length > 0 ? nh10Route : [];"""
geo_content = geo_content.replace(old_dest, new_dest)

# Find the Map JSX and add route layer + safety badge
# Look for the closing </Map> or the 3D button section to inject layers
route_layer_code = """
          {/* ROUTE SAFETY LAYER: colored line on map */}
          {resolvedRoute.length > 1 && (() => {
            const routeColor = routeSafety === 'CRITICAL' ? '#ef4444' :
              routeSafety === 'HIGH_RISK' ? '#f97316' :
              routeSafety === 'CAUTION' ? '#eab308' : '#22c55e';
            const routeGeoJSON = {
              type: 'FeatureCollection',
              features: [{
                type: 'Feature',
                properties: { safety: routeSafety },
                geometry: {
                  type: 'LineString',
                  coordinates: resolvedRoute.map((p: any) => [p[1], p[0]])
                }
              }]
            };
            return (
              <>
                <Source id="route-line-src" type="geojson" data={routeGeoJSON}>
                  <Layer
                    id="route-line-shadow"
                    type="line"
                    paint={{
                      'line-color': '#000000',
                      'line-width': 7,
                      'line-opacity': 0.3,
                      'line-blur': 3,
                    }}
                  />
                  <Layer
                    id="route-line"
                    type="line"
                    paint={{
                      'line-color': routeColor,
                      'line-width': 4,
                      'line-opacity': 0.9,
                      'line-dasharray': routeSafety === 'CRITICAL' ? [2, 1.5] : [1],
                    }}
                  />
                </Source>
              </>
            );
          })()}
"""

# Route Safety badge overlay on the map
route_badge_code = """
      {/* ROUTE SAFETY BADGE */}
      {routeSafety && routeSafety !== 'UNKNOWN' && (
        <div className="absolute top-3 left-3 z-10 pointer-events-none animate-in slide-in-from-left-4">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold tracking-wider shadow-lg backdrop-blur-md border ${
            routeSafety === 'CRITICAL' ? 'bg-red-500/20 border-red-500/40 text-red-300' :
            routeSafety === 'HIGH_RISK' ? 'bg-orange-500/20 border-orange-500/40 text-orange-300' :
            routeSafety === 'CAUTION' ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-300' :
            'bg-green-500/20 border-green-500/40 text-green-300'
          }`}>
            <span className={`w-2 h-2 rounded-full animate-pulse ${
              routeSafety === 'CRITICAL' ? 'bg-red-400' :
              routeSafety === 'HIGH_RISK' ? 'bg-orange-400' :
              routeSafety === 'CAUTION' ? 'bg-yellow-400' : 'bg-green-400'
            }`} />
            HIGHWAY: {routeSafety.replace('_', ' ')}
          </div>
        </div>
      )}
"""

# Insert route layer before the 3D button
geo_content = geo_content.replace(
    "{/* 3D TOGGLE BUTTON */}",
    route_layer_code + "\n      " + "{/* 3D TOGGLE BUTTON */}"
)

# Insert route badge after the opening map div
geo_content = geo_content.replace(
    "{/* 3D TOGGLE BUTTON */}",
    route_badge_code + "\n      {/* 3D TOGGLE BUTTON */}"
)

with open(geo_viewer_path, "w", encoding="utf-8") as f:
    f.write(geo_content)
print("GeospatialViewer.tsx: route layer + safety badge added")
print("ALL DONE")
