import re

filepath = r'C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\backend\main.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add region_id to get_latest_status
content = content.replace(
    "def get_latest_status():",
    "def get_latest_status(region_id: str = 'ner_india'):"
)

# Add region_id to get_active_warnings
content = content.replace(
    "def get_active_warnings():",
    "def get_active_warnings(region_id: str = 'ner_india'):"
)

# Add region_id to get_pending_verifications
content = content.replace(
    "def get_pending_verifications():",
    "def get_pending_verifications(region_id: str = 'ner_india'):"
)

# Add region_id to run_simulation stream generator
content = content.replace(
    "def run_simulation():",
    "def run_simulation(region_id: str = 'ner_india'):"
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
