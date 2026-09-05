import re

filepath = r'C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract everything from {/* SELECTED CELL DETAILS PANEL */} to the end of the file
start_marker = "{/* SELECTED CELL DETAILS PANEL */}"
start_idx = content.find(start_marker)

if start_idx != -1:
    new_block = '''{/* 3D TOGGLE BUTTON */}
      {selectedCell && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 animate-in slide-in-from-bottom-4 pointer-events-auto">
          {!is3D ? (
            <Button 
              onClick={() => handleExplore3D(selectedCell)}
              className="bg-teal-600/90 hover:bg-teal-500 backdrop-blur-sm text-white font-bold tracking-wider text-[10px] px-6 h-9 shadow-lg rounded-full"
            >
              <Navigation className="w-3.5 h-3.5 mr-2" />
              EXPLORE 3D TERRAIN
            </Button>
          ) : (
            <Button 
              onClick={handleReturnTo2D}
              variant="outline"
              className="bg-black/80 border-slate-600 text-slate-300 hover:bg-slate-800 hover:text-white backdrop-blur-sm font-bold tracking-wider text-[10px] px-6 h-9 shadow-lg rounded-full"
            >
              RETURN TO 2D OVERVIEW
            </Button>
          )}
        </div>
      )}

    </div>
  );
}
'''
    # We replace everything from start_marker to the end of the file
    content = content[:start_idx] + new_block

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("GeospatialViewer.tsx cleaned up!")
else:
    print("Marker not found!")
