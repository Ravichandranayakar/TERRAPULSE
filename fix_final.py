import re

# 1. FIX main.py
main_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\backend\main.py"
with open(main_path, "r", encoding="utf-8") as f:
    main_code = f.read()

old_return = """                "timestamp": pred["timestamp"] if pred else datetime.now().isoformat(),
            })
        return results
    finally:"""
new_return = """                "timestamp": pred["timestamp"] if pred else datetime.now().isoformat(),
            })
        from regions import get_region_data
        route = get_region_data(region_id).get('nh10_route', [])
        return {
            'cells': results,
            'route_safety': 'HIGH_RISK',
            'nh10_route': route,
            'region_id': region_id
        }
    finally:"""
main_code = main_code.replace(old_return, new_return)
with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_code)
print("main.py fixed!")

# 2. FIX GeospatialViewer.tsx
geo_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(geo_path, "r", encoding="utf-8") as f:
    geo = f.read()

# Change mapStyle
geo = geo.replace('satellite/style.json', 'hybrid/style.json')
geo = geo.replace('zoom: 9', 'zoom: 11')

# Add isScanning state
if "const [isScanning" not in geo:
    geo = geo.replace("const [saved2DState", "const [isScanning, setIsScanning] = useState(false);\n  const [saved2DState")

# Update Scan button UI
old_scan = """          {/* Scan this area button */}
          <div className="bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer pointer-events-auto hover:bg-emerald-500/30 transition-colors shadow-lg shadow-emerald-900/20">
            <span className="w-2.5 h-2.5 border-2 border-emerald-400 rounded-[2px]" /> Scan this area
          </div>"""

new_scan = """          {/* Scan this area button */}
          <div 
            onClick={() => { setIsScanning(true); setTimeout(() => setIsScanning(false), 2000); }}
            className={`backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer pointer-events-auto transition-colors shadow-lg ${isScanning ? 'bg-amber-500/20 border-amber-500/40 text-amber-400 shadow-amber-900/20 cursor-wait' : 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 shadow-emerald-900/20'}`}>
            {isScanning ? (
              <><span className="w-2.5 h-2.5 border-2 border-t-transparent border-amber-400 rounded-full animate-spin" /> Scanning Terrain...</>
            ) : (
              <><span className="w-2.5 h-2.5 border-2 border-emerald-400 rounded-[2px]" /> Scan this area</>
            )}
          </div>"""
geo = geo.replace(old_scan, new_scan)

# Remove the floating info card inside the map
# We find the <Card className="absolute bottom-6 right-6 ... pointer-events-auto"> block and remove it.
# We will preserve the RETURN TO 2D button by moving it up, but actually we can just put a standalone button at top right.

card_regex = re.compile(r'<Card className="absolute bottom-6 right-6.*?</Card>', re.DOTALL)
geo = card_regex.sub('', geo)

# Inject the Return to 2D Overview button standalone
return_btn = """
      {is3D && (
        <div className="absolute top-4 right-4 z-10">
          <Button 
            onClick={handleReturnTo2D}
            variant="outline"
            className="bg-black/80 backdrop-blur-md border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white font-medium text-xs h-8 shadow-lg"
          >
            <Navigation className="w-3.5 h-3.5 mr-2 rotate-180" />
            RETURN TO 2D OVERVIEW
          </Button>
        </div>
      )}
"""
# insert it before {/* MAPLIBRE GL CANVAS */}
geo = geo.replace('{/* MAPLIBRE GL CANVAS */}', return_btn + '\n      {/* MAPLIBRE GL CANVAS */}')

with open(geo_path, "w", encoding="utf-8") as f:
    f.write(geo)
print("GeospatialViewer fixed!")

