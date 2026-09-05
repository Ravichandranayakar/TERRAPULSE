import re

geo_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(geo_path, "r", encoding="utf-8") as f:
    geo = f.read()

# GeospatialViewer fix: Add resolvedRoute and useRegion if missing
if "const resolvedRoute" not in geo:
    # find where to inject it
    geo = geo.replace("  const [saved2DState, setSaved2DState] = useState<any>(null);", 
                      "  const [saved2DState, setSaved2DState] = useState<any>(null);\n  const resolvedRoute = nh10Route && nh10Route.length > 0 ? nh10Route : [];\n  const regionState = { region: cells[0]?.centroid_lon < 86 ? 'nepal_case' : 'sih_demo' };")

with open(geo_path, "w", encoding="utf-8") as f:
    f.write(geo)
print("GeospatialViewer fixed")

map_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(map_path, "r", encoding="utf-8") as f:
    map_code = f.read()

# LandslideMap fix: Update route drawing colors based on routeSafety
old_route = """          {/* NH-10 Highway Route */}
          {nh10Route && nh10Route.length > 1 && (
            <>
              {/* Glow effect */}
              <polyline
                points={nh10Route.map(([lat, lon]) => `${projectLon(lon, MAP_BOUNDS)},${projectLat(lat, MAP_BOUNDS)}`).join(' ')}
                fill="none"
                stroke="#60a5fa"
                strokeWidth="6"
                strokeOpacity="0.15"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Main route */}
              <polyline
                points={nh10Route.map(([lat, lon]) => `${projectLon(lon, MAP_BOUNDS)},${projectLat(lat, MAP_BOUNDS)}`).join(' ')}
                fill="none"
                stroke="#3b82f6"
                strokeWidth="2.5"
                strokeOpacity="0.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="8 3"
              />
              {/* NH-10 label */}
              <text
                x={projectLon(88.45, MAP_BOUNDS)}
                y={projectLat(27.30, MAP_BOUNDS) - 6}
                fill="#93c5fd"
                fontSize="8"
                fontWeight="bold"
                fontFamily="monospace"
                opacity="0.8"
              >
                NH-10
              </text>
            </>
          )}"""

new_route = """          {/* NH-10 Highway Route */}
          {nh10Route && nh10Route.length > 1 && (
            <>
              {/* Glow effect */}
              <polyline
                points={nh10Route.map(([lat, lon]) => `${projectLon(lon, MAP_BOUNDS)},${projectLat(lat, MAP_BOUNDS)}`).join(' ')}
                fill="none"
                stroke={routeSafety === 'CRITICAL' ? '#ef4444' : routeSafety === 'HIGH_RISK' ? '#f97316' : routeSafety === 'CAUTION' ? '#eab308' : '#60a5fa'}
                strokeWidth="6"
                strokeOpacity="0.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Main route */}
              <polyline
                points={nh10Route.map(([lat, lon]) => `${projectLon(lon, MAP_BOUNDS)},${projectLat(lat, MAP_BOUNDS)}`).join(' ')}
                fill="none"
                stroke={routeSafety === 'CRITICAL' ? '#b91c1c' : routeSafety === 'HIGH_RISK' ? '#c2410c' : routeSafety === 'CAUTION' ? '#a16207' : '#3b82f6'}
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={routeSafety === 'CRITICAL' ? '4 4' : '0'}
              />
              {/* Route label */}
              <text
                x={projectLon(nh10Route[Math.floor(nh10Route.length/2)][1], MAP_BOUNDS)}
                y={projectLat(nh10Route[Math.floor(nh10Route.length/2)][0], MAP_BOUNDS) - 6}
                fill="#93c5fd"
                fontSize="8"
                fontWeight="bold"
                opacity="0.8"
              >
                Regional Route
              </text>
            </>
          )}"""

map_code = map_code.replace(old_route, new_route)

# Inject badge back in
badge_html = """      {routeSafety && routeSafety !== 'UNKNOWN' && (
        <div className="absolute top-4 left-4 z-10 pointer-events-none">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold tracking-wider shadow-md border ${
            routeSafety === 'CRITICAL' ? 'bg-red-500/20 border-red-500/40 text-red-500' :
            routeSafety === 'HIGH_RISK' ? 'bg-orange-500/20 border-orange-500/40 text-orange-500' :
            routeSafety === 'CAUTION' ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-500' :
            'bg-green-500/20 border-green-500/40 text-green-500'
          }`}>
            <span className={`w-2 h-2 rounded-full animate-pulse ${
              routeSafety === 'CRITICAL' ? 'bg-red-500' :
              routeSafety === 'HIGH_RISK' ? 'bg-orange-500' :
              routeSafety === 'CAUTION' ? 'bg-yellow-500' : 'bg-green-500'
            }`} />
            ROUTE SAFETY: {routeSafety.replace('_', ' ')}
          </div>
        </div>
      )}"""

if "ROUTE SAFETY:" not in map_code:
    map_code = map_code.replace('<div className="relative w-full aspect-video bg-[#0f172a] rounded-lg overflow-hidden border border-slate-800">', '<div className="relative w-full aspect-video bg-[#0f172a] rounded-lg overflow-hidden border border-slate-800">\n' + badge_html)

with open(map_path, "w", encoding="utf-8") as f:
    f.write(map_code)
print("LandslideMap fixed")

