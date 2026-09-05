path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\backend\main.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_forecast = """@app.get("/api/forecast")
async def get_forecast(region_id: str = "ner_india"):
    \"\"\"
    Returns the 24-hour predictive risk trajectory for all monitored locations.
    \"\"\"
    try:
        locations = get_locations()
        forecast_result = await generate_24h_forecast(locations)"""

new_forecast = """@app.get("/api/forecast")
async def get_forecast(region_id: str = "ner_india"):
    \"\"\"
    Returns the 24-hour predictive risk trajectory for all monitored locations.
    \"\"\"
    try:
        if region_id == "nepal_case":
            from regions import get_region_data
            locations = get_region_data("nepal_case").get("grid_cells", [])
        else:
            locations = get_locations()
        forecast_result = await generate_24h_forecast(locations)"""

content = content.replace(old_forecast, new_forecast)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Forecast endpoint updated in main.py!")
