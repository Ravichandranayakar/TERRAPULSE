geo_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(geo_path, "r", encoding="utf-8") as f:
    geo_content = f.read()

# Add props
old_props = """  onCellClick?: (cell: GeoCell) => void,
  initialSelectedCellId?: string | null
})"""
new_props = """  onCellClick?: (cell: GeoCell) => void,
  initialSelectedCellId?: string | null,
  nh10Route?: any[],
  routeSafety?: string,
})"""
geo_content = geo_content.replace(old_props, new_props)

# Add destructuring
old_dest = """  const { state: regionState } = useRegion();"""
new_dest = """  const { state: regionState } = useRegion();
  const resolvedRoute = nh10Route && nh10Route.length > 0 ? nh10Route : [];"""
geo_content = geo_content.replace(old_dest, new_dest)

# Inject route layer INSIDE Map
# Search for </Map>
route_layer_code = """
        {/* ROUTE SAFETY LAYER: colored line on map */}
        {resolvedRoute.length > 1 && (() => {
          const routeColor = routeSafety === 'CRITICAL' ? '#ef4444' :
            routeSafety === 'HIGH_RISK' ? '#f97316' :
            routeSafety === 'CAUTION' ? '#eab308' : '#3b82f6'; // use blue if safe instead of green for realistic look
            
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
          
          // Generate a candidate slope buffer polygon (a wide path around the line) to replicate the UI requested
          // For visual purposes, we just render a thick line under it
          
          return (
            <>
              <Source id="route-line-src" type="geojson" data={routeGeoJSON}>
                <Layer
                  id="route-line-buffer"
                  type="line"
                  paint={{
                    'line-color': '#ef4444',
                    'line-width': 45,
                    'line-opacity': 0.15,
                    'line-blur': 15,
                  }}
                />
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
                    'line-width': 3,
                    'line-opacity': 0.9,
                  }}
                />
              </Source>
            </>
          );
        })()}
"""
geo_content = geo_content.replace("        )}\n      </Map>", "        )}\n" + route_layer_code + "      </Map>")

# Inject Candidate Slope UI and Badge OUTSIDE Map (after Map)
overlay_ui = """
      {/* MOCK UI FOR CANDIDATE SLOPE SCANNING (matches user image) */}
      {routeSafety && routeSafety !== 'UNKNOWN' && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 pointer-events-none flex flex-col items-center gap-2">
          {/* Main Candidate details */}
          <div className="bg-black/80 backdrop-blur-md border border-white/10 rounded-full pl-3 pr-1 py-1 flex items-center gap-3 shadow-xl shadow-red-900/20">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <div className="text-[10px] font-bold tracking-wide text-white leading-tight">
                Candidate slope near {regionState.region === 'nepal_case' ? 'Langtang Corridor' : 'NH-10'}<br/>
                <span className="text-red-400">HIGH - 85/100 - {regionState.region === 'nepal_case' ? '528.4' : '112.5'} km path</span>
              </div>
            </div>
            <div className="bg-white/10 hover:bg-white/20 text-white text-[10px] font-bold px-3 py-1.5 rounded-full cursor-pointer pointer-events-auto transition-colors">
              Details
            </div>
            <div className="bg-transparent hover:bg-white/10 text-white w-6 h-6 flex items-center justify-center rounded-full cursor-pointer pointer-events-auto">
              <span className="text-xs text-slate-400">&times;</span>
            </div>
          </div>
          
          {/* Scan this area button */}
          <div className="bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer pointer-events-auto hover:bg-emerald-500/30 transition-colors shadow-lg shadow-emerald-900/20">
            <span className="w-2.5 h-2.5 border-2 border-emerald-400 rounded-[2px]" /> Scan this area
          </div>
          
          {/* Detected count */}
          <div className="bg-black/60 backdrop-blur-sm px-3 py-1 rounded-full text-[9px] font-bold text-white tracking-widest mt-1">
            25 candidate slopes detected in view
          </div>
        </div>
      )}
"""
geo_content = geo_content.replace("{/* OVERLAY UI */}", "{/* OVERLAY UI */}\n" + overlay_ui)

with open(geo_path, "w", encoding="utf-8") as f:
    f.write(geo_content)
print("GeospatialViewer.tsx fixed properly")
