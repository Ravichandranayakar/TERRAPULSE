import re

filepath = r'C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\App.tsx'

with open(filepath, 'r', encoding='utf-8') as f:
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

# Fix dependencies for fetchAll
content = content.replace(
    "  }, []);\n\n  const fetchWarnings",
    "  }, [regionState.region]);\n\n  const fetchWarnings"
)

# Fix fetchWarnings
old_fetchwarnings = """  const fetchWarnings = useCallback(async () => {
    try {
      const w = await rpcCall({ func: 'get_active_warnings' });"""

new_fetchwarnings = """  const fetchWarnings = useCallback(async () => {
    try {
      const w = await rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } });"""

content = content.replace(old_fetchwarnings, new_fetchwarnings)

# Fix dependencies for fetchWarnings
content = content.replace(
    "  }, []);\n\n  const fetchPendingVerifications",
    "  }, [regionState.region]);\n\n  const fetchPendingVerifications"
)

# Fix fetchPendingVerifications
old_fetchpending = """  const fetchPendingVerifications = useCallback(async () => {
    try {
      const v = await rpcCall({ func: 'get_pending_verifications' });"""

new_fetchpending = """  const fetchPendingVerifications = useCallback(async () => {
    try {
      const v = await rpcCall({ func: 'get_pending_verifications', args: { region_id: regionState.region } });"""

content = content.replace(old_fetchpending, new_fetchpending)

# Fix dependencies for fetchPendingVerifications
content = content.replace(
    "  }, []);\n\n  const fetchModelInfo",
    "  }, [regionState.region]);\n\n  const fetchModelInfo"
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
