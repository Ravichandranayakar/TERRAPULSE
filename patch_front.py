import os

file_path = 'apps/terrapulse/frontend/src/features/StormSimulator.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add the function
if 'handleSaveRecord' not in content:
    func_code = '''
  const handleSaveRecord = async () => {
    try {
      const res = await rpcCall({
        func: 'save_simulation_record',
        args: { summary, events }
      });
      alert(res.message);
    } catch (e) {
      console.error(e);
      alert('Failed to save record.');
    }
  };
'''
    content = content.replace('const startSimulation = async () => {', func_code + '\n  const startSimulation = async () => {')

# Add the button where summary is rendered
if 'Save Simulation Record' not in content:
    button_code = '''
          {summary && (
            <Card className="bg-[#131313] border-border/20 rounded-xl overflow-hidden shadow-xl mt-4">
              <CardContent className="p-4 flex justify-between items-center">
                <span className="text-sm text-emerald-400 flex items-center gap-2"><CheckCircle className="w-4 h-4" /> Ready for Archive</span>
                <Button onClick={handleSaveRecord} variant="secondary" className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border-emerald-500/50">
                  Save Simulation Record
                </Button>
              </CardContent>
            </Card>
          )}
'''
    content = content.replace('      {/* Right Panel', button_code + '\n\n      {/* Right Panel')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Frontend updated successfully')
