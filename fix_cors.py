file_path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\backend\main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_cors = """app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""

new_cors = """app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""

content = content.replace(old_cors, new_cors)
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("CORS fixed in main.py")
