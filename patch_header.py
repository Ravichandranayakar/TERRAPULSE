import re

with open('apps/terrapulse/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
if 'useRegion' not in content:
    content = content.replace("import { rpcCall } from './api';", "import { rpcCall } from './api';\nimport { useRegion } from './contexts/RegionContext';")

# 2. Add hook
if 'const { state: regionState, setMode } = useRegion();' not in content:
    content = content.replace("export default function App() {\n", "export default function App() {\n  const { state: regionState, setMode } = useRegion();\n")

# 3. Fix the header
old_header = '''        {/* Header from Screenshot */}
        <header className="flex items-center justify-between px-5 md:px-8 py-5 border-b border-border/20 flex-shrink-0">
          <div className="flex items-center gap-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
            <span>NORTH SIKKIM CORRIDOR</span>
            <ChevronRight className="h-3 w-3" />
            <span className="text-white">{navItems.find(i => i.id === activeView)?.label}</span>
          </div>
          <div className="hidden sm:flex items-center gap-5">'''

new_header = '''        {/* Header from Screenshot */}
        <header className="flex items-center justify-between px-5 md:px-8 py-4 border-b border-border/20 flex-shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase min-w-[250px]">
              <span className={regionState.mode === 'case-study' ? 'text-amber-500' : 'text-primary'}>
                {regionState.mode === 'sih-demo' ? 'SIH DEMO ?" NER / INDIA' : 'REAL-WORLD CASE ?" NEPAL'}
              </span>
              <ChevronRight className="h-3 w-3" />
              <span className="text-white">{navItems.find(i => i.id === activeView)?.label}</span>
            </div>
            
            {/* Glassmorphism Mode Switcher */}
            <div className="hidden md:flex items-center bg-white/5 backdrop-blur-md border border-white/10 rounded-full p-1 ml-4">
              <button
                onClick={() => setMode('sih-demo')}
                className={px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 }
              >
                ???? SIH DEMO
              </button>
              <button
                onClick={() => setMode('case-study')}
                className={px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 }
              >
                ?? REAL-WORLD CASE
              </button>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-5">'''

content = content.replace(old_header, new_header)

with open('apps/terrapulse/frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
