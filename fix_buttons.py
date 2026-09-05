import re

with open('apps/terrapulse/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken classNames in the Mode Switcher buttons
bad_sih = "className={px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 }"
bad_case = "className={px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 }"

# We need to replace the entire block of buttons to be safe since they are mangled.
# Let's find the div for the Mode Switcher and replace its contents.
start_str = '{/* Glassmorphism Mode Switcher */}'
end_str = '</div>\n          <div className="hidden sm:flex items-center gap-5">'

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx != -1 and end_idx != -1:
    good_block = '''{/* Glassmorphism Mode Switcher */}
            <div className="hidden md:flex items-center bg-white/5 backdrop-blur-md border border-white/10 rounded-full p-1 ml-4">
              <button
                onClick={() => setMode('sih-demo')}
                className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 ${
                  regionState.mode === 'sih-demo' 
                    ? 'bg-primary text-black shadow-[0_0_15px_rgba(249,115,22,0.4)]' 
                    : 'text-muted-foreground hover:text-white hover:bg-white/5'
                }`}
              >
                ???? SIH DEMO
              </button>
              <button
                onClick={() => setMode('case-study')}
                className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 ${
                  regionState.mode === 'case-study' 
                    ? 'bg-amber-500 text-black shadow-[0_0_15px_rgba(245,158,11,0.4)]' 
                    : 'text-muted-foreground hover:text-white hover:bg-white/5'
                }`}
              >
                ?? REAL-WORLD CASE
              </button>
            '''
    
    content = content[:start_idx] + good_block + content[end_idx:]

with open('apps/terrapulse/frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
