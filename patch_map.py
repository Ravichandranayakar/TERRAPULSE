path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove cross mark from historical landslides
old_marker = """<text x={cx} y={cy + 1} textAnchor="middle" fill="#ffffff" fontSize="6" opacity="0.7">o </text>"""
new_marker = ""
content = content.replace(old_marker, new_marker)

# 2. Make route line thinner
old_stroke = "strokeWidth=\"6\""
new_stroke = "strokeWidth=\"3\""
content = content.replace(old_stroke, new_stroke)

# 3. Add Zoom Controls to SVG Map
import re

# Add state for zoom and pan
# We need to insert this into the LandslideMap component function
zoom_state_code = """
  const [zoom, setZoom] = React.useState(1);
  const handleZoomIn = () => setZoom(z => Math.min(z + 0.5, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.5, 1));
"""
# Find where the component starts
comp_start = "export function LandslideMap({ statusData, selectedCellId, onCellSelect, routeSafety, nh10Route, historicalLandslides, geoData }: any) {"
content = content.replace(comp_start, comp_start + zoom_state_code)

# Add buttons to the UI
ui_insertion_point = """      <CardContent className="flex-1 p-0 relative overflow-hidden min-h-[420px]">"""
ui_buttons = """      <CardContent className="flex-1 p-0 relative overflow-hidden min-h-[420px]">
        {/* Map Controls */}
        <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
          <button onClick={handleZoomIn} className="bg-slate-800/80 hover:bg-slate-700 text-white p-2 rounded border border-slate-600 backdrop-blur-sm" title="Zoom In">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          </button>
          <button onClick={handleZoomOut} className="bg-slate-800/80 hover:bg-slate-700 text-white p-2 rounded border border-slate-600 backdrop-blur-sm" title="Zoom Out">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          </button>
        </div>"""
content = content.replace(ui_insertion_point, ui_buttons)

# Apply scale transform to SVG contents
# Replace <svg ...> with <svg ...><g transform={`scale(${zoom}) transform-origin="center"`}>
svg_start = """        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="xMidYMid meet"
        >"""
svg_new_start = """        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="xMidYMid meet"
        >
          <g style={{ transform: `scale(${zoom})`, transformOrigin: 'center', transition: 'transform 0.3s ease' }}>"""
content = content.replace(svg_start, svg_new_start)

# Close the <g> before </svg>
svg_end = """          </svg>"""
svg_new_end = """          </g>
          </svg>"""
content = content.replace(svg_end, svg_new_end)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("LandslideMap updated")
