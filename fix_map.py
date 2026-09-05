app_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\App.tsx"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# Clear forecast data when changing region
fetch_all_start = """      setGeoData(geo);"""
fetch_all_fix = """      setGeoData(geo);
      setForecastData(null); // Clear forecast when region changes so it re-fetches"""
content = content.replace(fetch_all_start, fetch_all_fix)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("App.tsx 24h bug fixed")

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

# Fix MAP_BOUNDS to be dynamic based on cells
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
  return ((lon - bounds.lon_min) / (bounds.lon_max - bounds.lon_min)) * SVG_W;
}

function projectLat(lat: number, bounds: any): number {
  // Invert Y axis (higher lat = higher on screen)
  return SVG_H - ((lat - bounds.lat_min) / (bounds.lat_max - bounds.lat_min)) * SVG_H;
}"""
content = content.replace(old_bounds, new_bounds)

# Fix signature of LandslideMap
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

# Add dynamic bounding box logic
old_active = """  const activeCells = simulationCells && simulationCells.length > 0 ? simulationCells : cells;"""
new_active = """  const activeCells = simulationCells && simulationCells.length > 0 ? simulationCells : cells;

  const MAP_BOUNDS = React.useMemo(() => {
    if (!cells || cells.length === 0) return { lat_min: 27.10, lat_max: 27.75, lon_min: 88.25, lon_max: 88.70 };
    const lats = cells.map(c => c.centroid_lat);
    const lons = cells.map(c => c.centroid_lon);
    
    // Calculate precise bounding box with padding
    const padding = 0.1;
    const minLat = Math.min(...lats) - padding;
    const maxLat = Math.max(...lats) + padding;
    const minLon = Math.min(...lons) - padding;
    const maxLon = Math.max(...lons) + padding;
    
    // Scale map according to aspect ratio to prevent squishing
    const latDiff = maxLat - minLat;
    const lonDiff = maxLon - minLon;
    const targetRatio = SVG_W / SVG_H;
    const currentRatio = lonDiff / latDiff;
    
    let fMinLat = minLat, fMaxLat = maxLat, fMinLon = minLon, fMaxLon = maxLon;
    if (currentRatio > targetRatio) {
      // Too wide, need to add height (lat)
      const newLatDiff = lonDiff / targetRatio;
      const extra = (newLatDiff - latDiff) / 2;
      fMinLat -= extra; fMaxLat += extra;
    } else {
      // Too tall, need to add width (lon)
      const newLonDiff = latDiff * targetRatio;
      const extra = (newLonDiff - lonDiff) / 2;
      fMinLon -= extra; fMaxLon += extra;
    }
    
    return { lat_min: fMinLat, lat_max: fMaxLat, lon_min: fMinLon, lon_max: fMaxLon };
  }, [cells]);
  
  const routeColor = routeSafety === 'CRITICAL' ? '#ef4444' :
                     routeSafety === 'HIGH_RISK' ? '#f97316' :
                     routeSafety === 'CAUTION' ? '#eab308' : '#22c55e';
"""
content = content.replace(old_active, new_active)

# Replace projectLon(lon) and projectLat(lat) calls with projectLon(lon, MAP_BOUNDS) and projectLat(lat, MAP_BOUNDS)
import re
content = re.sub(r'projectLon\(([^,)]+)\)', r'projectLon(\1, MAP_BOUNDS)', content)
content = re.sub(r'projectLat\(([^,)]+)\)', r'projectLat(\1, MAP_BOUNDS)', content)

# Replace route color
content = content.replace("stroke=\"#94a3b8\"", "stroke={routeColor}")
content = content.replace("strokeDasharray=\"4 4\"", "strokeDasharray={routeSafety === 'CRITICAL' ? '4 4' : '0'}")

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
            HIGHWAY: {routeSafety.replace('_', ' ')}
          </div>
        </div>
      )}"""
content = content.replace('<div className="relative w-full aspect-video bg-[#0f172a] rounded-lg overflow-hidden border border-slate-800">', '<div className="relative w-full aspect-video bg-[#0f172a] rounded-lg overflow-hidden border border-slate-800">\n' + badge_html)

with open(map_path, "w", encoding="utf-8") as f:
    f.write(content)
print("LandslideMap.tsx dynamic bounding box and route safety added")
