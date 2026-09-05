import re

with open('apps/terrapulse/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix fetchAll
old_fetchall = """  const fetchAll = useCallback(async () => {
    try {
      const [geo, status, activeWarnings] = await Promise.all([
        rpcCall({ func: 'get_geo_data' }),
        rpcCall({ func: 'get_latest_status' }),
        rpcCall({ func: 'get_active_warnings' }),
      ]);"""

new_fetchall = """  const fetchAll = useCallback(async () => {
    try {
      const [geo, status, activeWarnings] = await Promise.all([
        rpcCall({ func: 'get_geo_data', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_latest_status', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } }),
      ]);"""

content = content.replace(old_fetchall, new_fetchall)

# Fix fetchAll dependencies
content = content.replace(
    "  }, []);\n\n  const fetchWarnings",
    "  }, [regionState.region]);\n\n  const fetchWarnings"
)

# Fix fetchWarnings (just in case it's called independently)
old_fetchwarn = """  const fetchWarnings = useCallback(async () => {
    try {
      const w = await rpcCall({ func: 'get_active_warnings' });"""
      
new_fetchwarn = """  const fetchWarnings = useCallback(async () => {
    try {
      const w = await rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } });"""

content = content.replace(old_fetchwarn, new_fetchwarn)
content = content.replace(
    "  }, []);\n\n  const fetchPendingVerifications",
    "  }, [regionState.region]);\n\n  const fetchPendingVerifications"
)

with open('apps/terrapulse/frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
