path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Determine if Nepal mode is active based on the first cell's longitude
old_comp_start = """export function LandslideMap({
  cells,
  nh10Route,
  routeSafety,
  historicalLandslides,
  selectedCellId,
  onCellSelect,
  simulationCells,
}: LandslideMapProps) {"""

new_comp_start = """export function LandslideMap({
  cells,
  nh10Route,
  routeSafety,
  historicalLandslides,
  selectedCellId,
  onCellSelect,
  simulationCells,
}: LandslideMapProps) {
  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;
  const mapTitle = isNepal ? "Rasuwa District - Landslide Risk Map" : "North Sikkim - Landslide Risk Map";
  const mapSubtitle = isNepal ? "HIMALAYAS - NEPAL" : "NER - INDIA";
  const svgOverlayTitle = isNepal ? "Langtang Region, Rasuwa" : "Mangan District, North Sikkim";
"""
content = content.replace(old_comp_start, new_comp_start)

# Update Card Title
old_card_title = """<CardTitle className="font-heading flex items-center gap-2 text-base">
            <MapPin className="h-5 w-5 text-primary" />
            North Sikkim - Landslide Risk Map
            <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider ml-1">
              NER - India
            </Badge>
          </CardTitle>"""
new_card_title = """<CardTitle className="font-heading flex items-center gap-2 text-base">
            <MapPin className="h-5 w-5 text-primary" />
            {mapTitle}
            <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider ml-1">
              {mapSubtitle}
            </Badge>
          </CardTitle>"""
# Sometimes there are weird unicode chars, let's use regex for safety
import re
content = re.sub(r'<CardTitle className="font-heading flex items-center gap-2 text-base">.*?<\/CardTitle>', new_card_title, content, flags=re.DOTALL)

# Update SVG Text Title
old_svg_title = """{/* Map title overlay */}
          <text x={10} y={18} fill="#e2e8f0" fontSize="11" fontWeight="bold" fontFamily="system-ui" opacity="0.8">
            Mangan District, North Sikkim
          </text>"""
new_svg_title = """{/* Map title overlay */}
          <text x={10} y={18} fill="#e2e8f0" fontSize="11" fontWeight="bold" fontFamily="system-ui" opacity="0.8">
            {svgOverlayTitle}
          </text>"""
content = content.replace(old_svg_title, new_svg_title)

# Update Highway Text
old_highway_text = """<span className="inline-block h-2 w-4 border border-blue-400/60 bg-blue-400/20" />
            NH-10 Highway
          </span>"""
new_highway_text = """<span className="inline-block h-2 w-4 border border-blue-400/60 bg-blue-400/20" />
            {isNepal ? 'H01 Trishuli Highway' : 'NH-10 Highway'}
          </span>"""
content = content.replace(old_highway_text, new_highway_text)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("LandslideMap updated")
