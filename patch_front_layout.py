import re

file_path = 'apps/terrapulse/frontend/src/features/StormSimulator.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove old block (find the block right before Right Panel)
old_block = '''          {summary && (
            <Card className="bg-[#131313] border-border/20 rounded-xl overflow-hidden shadow-xl mt-4">
              <CardContent className="p-4 flex justify-between items-center">
                <span className="text-sm text-emerald-400 flex items-center gap-2"><CheckCircle className="w-4 h-4" /> Ready for Archive</span>
                <Button onClick={handleSaveRecord} variant="secondary" className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border-emerald-500/50">
                  Save Simulation Record
                </Button>
              </CardContent>
            </Card>
          )}'''
content = content.replace(old_block, "")

# 2. Add the block below the ML Pipeline text
target = '''                  {isStreaming && (
                    <div className="flex items-center justify-center p-4">
                      <Loader2 className="h-5 w-5 animate-spin text-primary opacity-60 mr-2" />
                      <span className="text-xs text-muted-foreground">Processing through ML pipeline...</span>
                    </div>
                  )}'''

new_block = '''                  {isStreaming && (
                    <div className="flex items-center justify-center p-4">
                      <Loader2 className="h-5 w-5 animate-spin text-primary opacity-60 mr-2" />
                      <span className="text-xs text-muted-foreground">Processing through ML pipeline...</span>
                    </div>
                  )}
                  {summary && (
                    <div className="mt-4 p-4 border border-emerald-500/30 rounded-lg bg-[#1a1a1a] flex justify-between items-center shadow-lg mx-4 mb-4">
                      <span className="text-sm text-emerald-400 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" /> Ready for Archive
                      </span>
                      <Button onClick={handleSaveRecord} variant="secondary" className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border-emerald-500/50">
                        Save Record
                      </Button>
                    </div>
                  )}'''

if '{summary && (' not in content.split('ML pipeline')[1][:300]:
    content = content.replace(target, new_block)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Frontend layout updated successfully')
