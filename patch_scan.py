path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Update the scan UI text and positioning
old_ui = """        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3">
          {selectedCellId ? (
            <div className="bg-black/90 text-white px-4 py-2 rounded-full text-xs font-bold flex items-center gap-3 border border-red-500/30">
              <div className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
              Candidate slope near NH-10
              <span className="text-red-400">HIGH - 85/100 - 112.5 km path</span>
              <button className="bg-white/10 hover:bg-white/20 px-2 py-1 rounded">Details</button>
            </div>
          ) : (
            <>
              <button 
                onClick={handleScan}
                disabled={isScanning}
                className="bg-emerald-600/60 hover:bg-emerald-500/70 border border-emerald-400/50 backdrop-blur-md text-white font-bold tracking-widest uppercase px-8 py-3 rounded-full text-xs flex items-center gap-2 transition-all"
              >
                {isScanning ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Square className="h-4 w-4" />
                )}
                {isScanning ? 'Running Analysis...' : 'Scan This Area'}
              </button>
              <div className="bg-[#422006]/90 text-white px-4 py-1.5 rounded-full text-xs font-bold">
                25 candidate slopes detected in view
              </div>
            </>
          )}
        </div>"""

new_ui = """        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3">
          {selectedCellId ? (
            <div className="bg-black/90 text-white px-4 py-2 rounded-full text-xs font-bold flex items-center gap-3 border border-red-500/30 shadow-lg">
              <div className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
              Terrain Profile Analyzed
              <span className="text-red-400">Vulnerability: High</span>
            </div>
          ) : (
            <>
              <button 
                onClick={handleScan}
                disabled={isScanning}
                className="bg-emerald-600/60 hover:bg-emerald-500/70 border border-emerald-400/50 backdrop-blur-md text-white font-bold tracking-widest uppercase px-8 py-3 rounded-full text-xs flex items-center gap-2 transition-all shadow-lg"
              >
                {isScanning ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h4v4H4z"></path><path d="M16 4h4v4h-4z"></path><path d="M4 16h4v4H4z"></path><path d="M16 16h4v4h-4z"></path><path d="M12 2v20"></path><path d="M2 12h20"></path></svg>
                )}
                {isScanning ? 'Running ML Inference...' : 'Satellite Inference Scan'}
              </button>
              <div className="bg-[#422006]/90 text-white px-4 py-1.5 rounded-full text-[11px] font-bold shadow-md">
                12 High-Risk Topologies Detected in Region
              </div>
            </>
          )}
        </div>"""

content = content.replace(old_ui, new_ui)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("GeospatialViewer updated")
