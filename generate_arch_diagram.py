import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Output path
output_dir = os.path.join(os.getcwd(), 'model_graphs')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'system_architecture_diagram.png')

fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
ax.set_xlim(0, 16)
ax.set_ylim(0, 11)
ax.axis('off')
fig.patch.set_facecolor('#ffffff')

# Colors
C_SOURCE = '#e0f2fe'      # Sky 100
C_SOURCE_B = '#0284c7'    # Sky 600
C_PIPE = '#f1f5f9'        # Slate 100
C_PIPE_B = '#475569'      # Slate 600
C_STATIC = '#dcfce7'      # Green 100
C_STATIC_B = '#16a34a'    # Green 600
C_DYN = '#fef3c7'         # Amber 100
C_DYN_B = '#d97706'       # Amber 600
C_FUSION = '#fae8ff'      # Purple 100
C_FUSION_B = '#9333ea'    # Purple 600
C_API = '#e2e8f0'         # Slate 200
C_API_B = '#1e293b'       # Slate 800
C_OUT = '#ede9fe'         # Violet 100
C_OUT_B = '#7c3aed'       # Violet 600
C_HITL = '#ffedd5'        # Orange 100
C_HITL_B = '#ea580c'      # Orange 600

def draw_box(x, y, w, h, bg, border, title, text="", title_size=11, text_size=9, radius=0.15):
    p = patches.FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad={radius}",
                               facecolor=bg, edgecolor=border, linewidth=1.8)
    ax.add_patch(p)
    if text:
        ax.text(x + w/2, y + h*0.68, title, ha='center', va='center', fontsize=title_size, fontweight='bold', color='#0f172a')
        ax.text(x + w/2, y + h*0.35, text, ha='center', va='center', fontsize=text_size, color='#334155', linespacing=1.3)
    else:
        ax.text(x + w/2, y + h/2, title, ha='center', va='center', fontsize=title_size, fontweight='bold', color='#0f172a')

def draw_arrow(x1, y1, x2, y2, color='#475569', style='->', lw=1.8):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=3, shrinkB=3))

# Header Title
ax.text(8, 10.5, "TerraPulse.ai — System Architecture & Implementation", ha='center', va='center',
        fontsize=18, fontweight='bold', color='#0f172a')
ax.text(8, 10.15, "Decoupled Dual-Engine Early Warning & Hazard Assessment Architecture", ha='center', va='center',
        fontsize=12, color='#64748b', style='italic')

# ----------------- LAYER 1: DATA SOURCES -----------------
draw_box(0.8, 8.6, 6.8, 1.1, C_SOURCE, C_SOURCE_B,
         "1A. Meteorological & In-Situ Data",
         "• NASA GPM & IMD Rainfall   • SMAP / ESA Soil Moisture   • Open-Meteo 24h Forecast")

draw_box(8.4, 8.6, 6.8, 1.1, C_SOURCE, C_SOURCE_B,
         "1B. Geospatial & Satellite Data",
         "• SRTM 30m DEM Elevation   • Bhuvan Geomorphology & Lineaments   • OSM Roads/Rivers")

# ----------------- LAYER 2: 7-STAGE ETL PIPELINE -----------------
draw_box(0.8, 7.0, 14.4, 1.0, C_PIPE, C_PIPE_B,
         "2. 7-STAGE ETL & SPATIAL ENGINE (Rasterio, PyOGRio, GeoPandas)",
         "Raw Ingestion  ➜  EPSG:4326 Normalization  ➜  Slope/Aspect/TWI Derivations  ➜  41-Feature Matrix Assembly")

draw_arrow(4.2, 8.6, 4.2, 8.0)
draw_arrow(11.8, 8.6, 11.8, 8.0)

# ----------------- LAYER 3: DUAL ENGINE -----------------
# Static
draw_box(0.8, 5.0, 6.8, 1.4, C_STATIC, C_STATIC_B,
         "3A. STATIC SUSCEPTIBILITY ENGINE (WHERE?)",
         "• LightGBM ML Model (models/landslide_v0.4, 600 trees, 41 features)\n• Evaluates slope gradient, lithology, soil clay %, road proximity\n• Output: Static Susceptibility Score S in [0, 1]")

# Dynamic
draw_box(8.4, 5.0, 6.8, 1.4, C_DYN, C_DYN_B,
         "3B. DYNAMIC METEOROLOGICAL ENGINE (WHEN?)",
         "• Antecedent Precipitation Index (1h, 24h, 3-day accumulated)\n• Real-time SMAP root-zone soil saturation & 24h forward forecast\n• Output: Dynamic Trigger Score T in [0, 1]")

draw_arrow(4.2, 7.0, 4.2, 6.4)
draw_arrow(11.8, 7.0, 11.8, 6.4)

# ----------------- OPERATIONAL RISK FUSION -----------------
draw_box(3.5, 3.8, 9.0, 0.8, C_FUSION, C_FUSION_B,
         "OPERATIONAL RISK FUSION MODULE",
         "R_op = max(S_static, T_dynamic) * (1 + alpha * S * T)   |   alpha = 0.25 (Interaction Factor)",
         title_size=11, text_size=9)

draw_arrow(4.2, 5.0, 6.0, 4.6)
draw_arrow(11.8, 5.0, 10.0, 4.6)

# ----------------- LAYER 4: FASTAPI & STORAGE -----------------
draw_box(0.8, 2.3, 14.4, 1.1, C_API, C_API_B,
         "4. FASTAPI CORE BACKEND & STORAGE TIERS",
         "API Services: /api/risk/*  •  /api/live/*  •  /api/verification/*  •  /api/alerts/*\nDatabases: SQLite (Incident State & Audits)  •  PostgreSQL 16 + PostGIS 3.6 (Spatial Corridors)  •  Model Registry")

draw_arrow(8.0, 3.8, 8.0, 3.4)

# ----------------- LAYER 5: FRONTEND & DISPATCH -----------------
draw_box(0.8, 0.6, 7.0, 1.3, C_OUT, C_OUT_B,
         "5A. REACT 18 + VITE FRONTEND",
         "• MapLibre GL 2D / 3D Terrain & Satellite Imagery\n• Storm Simulator (Strict State Isolation Sandbox)\n• Citizen Mobile Reporting Portal  •  Curator Review",
         text_size=8.5)

draw_box(8.2, 0.6, 7.0, 1.3, C_HITL, C_HITL_B,
         "5B. MULTI-CHANNEL DISPATCH & HITL",
         "• CAP 1.2 Common Alerting Protocol Generator (EN, HI, NE)\n• Simulated Cell Broadcast Gateway (NDMA/C-DOT specification)\n• Live Mobile Push (ntfy.sh)  •  Gated Offline Model Retraining",
         text_size=8.5)

draw_arrow(4.3, 2.3, 4.3, 1.9)
draw_arrow(11.7, 2.3, 11.7, 1.9)

plt.tight_layout()
plt.savefig(output_path, bbox_inches='tight')
plt.close()
print("Generated system_architecture_diagram.png successfully at:", output_path)

