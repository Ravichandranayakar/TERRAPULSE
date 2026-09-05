map_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(map_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add routeSafety to props
old_props = """interface LandslideMapProps {
  cells: GeoCell[];
  nh10Route: number[][];
  historicalLandslides: HistoricalLandslide[];
  selectedCellId: string | null;
  onCellSelect: (id: string) => void;
  simulationCells?: GeoCell[];
}"""
new_props = """interface LandslideMapProps {
  cells: GeoCell[];
  nh10Route: number[][];
  routeSafety?: string;
  historicalLandslides: HistoricalLandslide[];
  selectedCellId: string | null;
  onCellSelect: (id: string) => void;
  simulationCells?: GeoCell[];
}"""
content = content.replace(old_props, new_props)

# Fix MAP_BOUNDS to be dynamic
old_bounds = """const MAP_BOUNDS = {
  lat_min: 27.10,
  lat_max: 27.75,
  lon_min: 88.25,
  lon_max: 88.70,
};

const SVG_W = 900;
const SVG_H = 550;

function projectLon(lon: number): number {
  return ((lon - MAP_BOUNDS.lon_min) / (MAP_BOUNDS.lon_max - MAP_BOUNDS.lon_min)) * SVG_W;
}

function projectLat(lat: number): number {
  // Invert Y axis (higher lat = higher on screen)
  return SVG_H - ((lat - MAP_BOUNDS.lat_min) / (MAP_BOUNDS.lat_max - MAP_BOUNDS.lat_min)) * SVG_H;
}"""

new_bounds = """const SVG_W = 900;
const SVG_H = 550;

function projectLon(lon: number, bounds: any): number {
  if (!bounds || bounds.lon_max === bounds.lon_min) return SVG_W / 2;
  return ((lon - bounds.lon_min) / (bounds.lon_max - bounds.lon_min)) * SVG_W;
}

function projectLat(lat: number, bounds: any): number {
  if (!bounds || bounds.lat_max === bounds.lat_min) return SVG_H / 2;
  return SVG_H - ((lat - bounds.lat_min) / (bounds.lat_max - bounds.lat_min)) * SVG_H;
}"""
content = content.replace(old_bounds, new_bounds)

# Fix signature
old_sig = """export function LandslideMap({
  cells,
  nh10Route,
  historicalLandslides,
  selectedCellId,
  onCellSelect,
  simulationCells,
}: LandslideMapProps) {"""
new_sig = """export function LandslideMap({
  cells,
  nh10Route,
  routeSafety,
  historicalLandslides,
  selectedCellId,
  onCellSelect,
  simulationCells,
}: LandslideMapProps) {"""
content = content.replace(old_sig, new_sig)

# Add dynamic bounding box logic inside component
old_active = """  const activeCells = simulationCells && simulationCells.length > 0 ? simulationCells : cells;"""
new_active = """  const activeCells = simulationCells && simulationCells.length > 0 ? simulationCells : cells;

  const MAP_BOUNDS = React.useMemo(() => {
    if (!cells || cells.length === 0) return { lat_min: 27.10, lat_max: 27.75, lon_min: 88.25, lon_max: 88.70 };
    const lats = cells.map(c => c.centroid_lat);
    const lons = cells.map(c => c.centroid_lon);
    
    // Calculate precise bounding box
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    
    // Add margin (roughly 10% of the range)
    const latMargin = Math.max(0.05, (maxLat - minLat) * 0.15);
    const lonMargin = Math.max(0.05, (maxLon - minLon) * 0.15);
    
    return { 
      lat_min: minLat - latMargin, 
      lat_max: maxLat + latMargin, 
      lon_min: minLon - lonMargin, 
      lon_max: maxLon + lonMargin 
    };
  }, [cells]);
  
  // Dynamic grid lines based on bounds
  const latLines = React.useMemo(() => {
    const lines = [];
    const step = (MAP_BOUNDS.lat_max - MAP_BOUNDS.lat_min) / 5;
    for(let i=1; i<5; i++) lines.push(MAP_BOUNDS.lat_min + (step * i));
    return lines;
  }, [MAP_BOUNDS]);

  const lonLines = React.useMemo(() => {
    const lines = [];
    const step = (MAP_BOUNDS.lon_max - MAP_BOUNDS.lon_min) / 5;
    for(let i=1; i<5; i++) lines.push(MAP_BOUNDS.lon_min + (step * i));
    return lines;
  }, [MAP_BOUNDS]);
"""
content = content.replace(old_active, new_active)

# Replace projectLon(lon) with projectLon(lon, MAP_BOUNDS) everywhere
import re
content = re.sub(r'projectLon\(([^,)]+)\)', r'projectLon(\1, MAP_BOUNDS)', content)
content = re.sub(r'projectLat\(([^,)]+)\)', r'projectLat(\1, MAP_BOUNDS)', content)

# Fix hardcoded grid lines
old_grid = """          <g opacity="0.07">
            {[27.1, 27.2, 27.3, 27.4, 27.5, 27.6, 27.7].map(lat => (
              <line key={lat}
                x1={0} y1={projectLat(lat, MAP_BOUNDS)}
                x2={SVG_W} y2={projectLat(lat, MAP_BOUNDS)}
                stroke="#6ee7b7" strokeWidth="1" />
            ))}
            {[88.25, 88.35, 88.45, 88.55, 88.65].map(lon => (
              <line key={lon}
                x1={projectLon(lon, MAP_BOUNDS)} y1={0}
                x2={projectLon(lon, MAP_BOUNDS)} y2={SVG_H}
                stroke="#6ee7b7" strokeWidth="1" />
            ))}
          </g>

          {/* Coordinate labels */}
          <g fill="#6ee7b7" opacity="0.25" fontSize="9" fontFamily="monospace">
            {[27.2, 27.4, 27.6].map(lat => (
              <text key={lat} x={4} y={projectLat(lat, MAP_BOUNDS) - 2}>{lat.toFixed(1)}°N</text>
            ))}
            {[88.3, 88.5, 88.65].map(lon => (
              <text key={lon} x={projectLon(lon, MAP_BOUNDS) + 2} y={SVG_H - 4}>{lon.toFixed(1)}°E</text>
            ))}
          </g>"""

new_grid = """          <g opacity="0.07">
            {latLines.map(lat => (
              <line key={lat}
                x1={0} y1={projectLat(lat, MAP_BOUNDS)}
                x2={SVG_W} y2={projectLat(lat, MAP_BOUNDS)}
                stroke="#6ee7b7" strokeWidth="1" />
            ))}
            {lonLines.map(lon => (
              <line key={lon}
                x1={projectLon(lon, MAP_BOUNDS)} y1={0}
                x2={projectLon(lon, MAP_BOUNDS)} y2={SVG_H}
                stroke="#6ee7b7" strokeWidth="1" />
            ))}
          </g>

          {/* Coordinate labels */}
          <g fill="#6ee7b7" opacity="0.25" fontSize="9" fontFamily="monospace">
            {latLines.map(lat => (
              <text key={lat} x={4} y={projectLat(lat, MAP_BOUNDS) - 2}>{lat.toFixed(2)}°N</text>
            ))}
            {lonLines.map(lon => (
              <text key={lon} x={projectLon(lon, MAP_BOUNDS) + 2} y={SVG_H - 4}>{lon.toFixed(2)}°E</text>
            ))}
          </g>"""
content = content.replace(old_grid, new_grid)

# Fix NH10 Route label
old_label = """              {/* NH-10 label */}
              <text
                x={projectLon(88.45, MAP_BOUNDS)}
                y={projectLat(27.30, MAP_BOUNDS) - 6}
                fill="#93c5fd"
                fontSize="8"
                fontWeight="bold"
                opacity="0.8"
              >
                NH-10 Highway
              </text>"""
new_label = """              {/* Route label */}
              {nh10Route.length > 0 && (
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
              )}"""
content = content.replace(old_label, new_label)

# Add Route Safety overlay indicator for the 2D map
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
content = content.replace('<div className="relative w-full aspect-video bg-[#0f172a] rounded-lg overflow-hidden border border-slate-800">', '<div className="relative w-full aspect-video bg-[#0f172a] rounded-lg overflow-hidden border border-slate-800">\n' + badge_html)

with open(map_path, "w", encoding="utf-8") as f:
    f.write(content)
print("LandslideMap.tsx fixed properly")
