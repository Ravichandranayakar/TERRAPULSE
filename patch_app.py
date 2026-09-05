path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\App.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Move the toggle button to bottom-middle
old_btn = """<Button 
                    variant="outline"
                    className="absolute bottom-4 left-4 z-10 bg-black/60 backdrop-blur-md border-teal-500/30 hover:bg-teal-900/40 text-teal-300 rounded-full h-12 w-12 p-0"
                    onClick={() => setUseMapLibre(!useMapLibre)}"""

new_btn = """<Button 
                    variant="outline"
                    className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 bg-black/60 backdrop-blur-md border-teal-500/30 hover:bg-teal-900/40 text-teal-300 rounded-full h-12 px-6 flex items-center gap-2"
                    onClick={() => setUseMapLibre(!useMapLibre)}"""

content = content.replace(old_btn, new_btn)

# Add text to the button to make it more obvious
old_icon = """<Globe className="h-5 w-5" />
                  </Button>"""
new_icon = """<Globe className="h-5 w-5" />
                    <span className="text-xs font-bold uppercase tracking-wider">{useMapLibre ? '2D View' : '3D View'}</span>
                  </Button>"""

content = content.replace(old_icon, new_icon)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("App.tsx updated")
