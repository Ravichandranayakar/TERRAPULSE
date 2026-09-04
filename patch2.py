file_path = 'apps/terrapulse/frontend/src/features/StormSimulator.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'Processing through ML pipeline...</span>\n                    </div>\n                  )}'

new_block = '''Processing through ML pipeline...</span>
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

if '{summary && (' not in content.split('ML pipeline...</span>')[1][:300]:
    content = content.replace(target, new_block)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Inserted successfully!')
else:
    print('Already inserted or target not found.')
