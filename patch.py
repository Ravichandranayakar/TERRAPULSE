import os, json, time
from datetime import datetime

file_path = 'apps/terrapulse/backend/main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add the save_simulation_record function
record_func = '''
def save_simulation_record(summary: dict, events: list):
    \"\"\"Save the simulation summary and events as a permanent JSON record.\"\"\"
    records_dir = os.path.join(os.path.dirname(__file__), "data", "records")
    os.makedirs(records_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sim_record_{timestamp}.json"
    filepath = os.path.join(records_dir, filename)
    
    record = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "events": events
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        
    return {"success": True, "file": filename, "message": "Simulation record saved."}
'''

if 'def save_simulation_record' not in content:
    content = content.replace('def reset_simulation():', record_func + '\n\ndef reset_simulation():')

# 2. Add to __all__
if '\"save_simulation_record\",' not in content:
    content = content.replace('\"reset_simulation\",', '\"save_simulation_record\",\n    \"reset_simulation\",')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Backend updated successfully')
