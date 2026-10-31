# TerraPulse.ai

**Live Demo:** [https://terrapulse-86te.onrender.com/](https://terrapulse-86te.onrender.com/)
**AI-Based Early Warning and Landslide Risk Monitoring System in the North Eastern Region (NER)**

*SIH 2026 Problem Statement: SIH26001*

## Overview
TerraPulse.ai is a next-generation predictive intelligence platform designed for the complex geological terrain of the North Eastern Region (NER) of India, specifically focusing on the critical NH-10 highway corridor in North Sikkim.

A LightGBM susceptibility model, trained on 17,092 points derived from the GSI landslide
inventory, scores each monitoring cell from real terrain, soil, land-cover, distance,
rainfall-climatology, and GSI/Bhuvan geomorphology and lineament features. On top of that
ranking, a separate live trigger layer watches measured rainfall and soil moisture and
raises the alert level when conditions match those recorded against historical events.

## Key Features

1. **Temporal Storm Simulator:** Replays extreme monsoon scenarios (T+0 to T+50) through the live ML pipeline.
2. **Explainable AI (XAI) Panel:** Transparently visualizes top risk drivers (Rainfall Intensity, Slope Angle) for each geographic cell.
3. **Infrastructure Impact Assessment:** Automatically detects risk propagation onto critical infrastructure (NH-10).
4. **Human-in-the-Loop (HITL) Curation:** Integrates SDRF field verification reports before adding them to the ML training dataset, preventing noisy data from degrading the model.

## Tech Stack
* **Frontend:** React, Tailwind CSS, Vite, Lucide-React, Recharts (EOC Control Room Dark Aesthetic)
* **Backend:** FastAPI, Python 3
* **Machine Learning:** LightGBM (the active model), XGBoost and scikit-learn Random
  Forest (measured in the same run), Pandas, NumPy
* **Geospatial:** rasterio, geopandas, pyogrio, shapely; Copernicus DEM, ESA WorldCover,
  SoilGrids, OpenStreetMap, Bhuvan (ISRO/NRSC) geomorphology and lineaments
* **Database:** SQLite for application state, PostgreSQL 16 + PostGIS 3.6 for spatial queries

## How It Works

The operational path runs on a timer and never trains anything:

```text
live sources
    -> 01 data ingestion
    -> 02 data preprocessing
    -> 03 geo processing
    -> 04 feature engineering
    -> 05 load the trained model
    -> 06 risk engine
    -> 07 map + alerts
```

Stages 01-04 assemble a feature vector for each monitoring cell. Stage 05 loads the
saved artifact. Inference takes about 46 ms per cell.

The whole path is orchestrated by `apps/terrapulse/backend/pipeline.py`:

```bash
python pipeline.py                  full pipeline, human readable
python pipeline.py --json           machine readable
python pipeline.py --stages 01,04   selected stages
python pipeline.py --live           runtime inference path only
python pipeline.py --feedback       check/run the retraining cycle
```

Retraining is **not** part of this path. It is a separate offline process
(`feedback_loop.py`) that promotes a candidate only when validation does not regress.

### Where the numbers come from

| Feature group | Source | New data arrives |
|---|---|---|
| Elevation, slope, curvature, aspect | Copernicus DEM GLO-30 | yearly |
| Land cover | ESA WorldCover 2021 | yearly |
| Soil texture | SoilGrids | effectively static |
| Rainfall climatology | IMD gridded, 1991-2025 | daily |
| Distance to roads, rivers | OpenStreetMap | continuous |
| Live rainfall, soil moisture | Open-Meteo | hourly |

No feature value is typed in by hand. Each one is computed from its source file at
the coordinate being scored, and the pipeline rebuilds them automatically when a
source dataset is republished.

## Local Development Setup

### 1. Backend Server
Navigate to the backend directory and run the FastAPI server:
```bash
cd apps/terrapulse/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 5000
```

### 2. Frontend Application
Navigate to the frontend directory and start the Vite dev server:
```bash
cd apps/terrapulse/frontend
npm run dev
```

## Storm Simulator and the Development Predictor

The Storm Simulator currently uses the development risk contract rather than a
trained or validated machine-learning model. Scenario feature values are sent
to `POST /api/risk/predict-batch`, normalized by the backend, and evaluated by
`DevelopmentRiskPredictor`. The response contains a deterministic score,
`LOW`/`MODERATE`/`HIGH`/`CRITICAL` class, interpretable drivers, and a
warning-ready flag. The score is an internal development indicator, not a
probability or scientifically validated prediction.

The frontend keeps the response in the existing `simulationCells` state, which
is merged into `displayCells` and consumed by both MapLibre 2D and 3D views.
The trained susceptibility model is served behind the same risk service contract at
`/api/risk/predict-trained`, and the live cycle uses it for every monitoring cell. The
simulator still runs on the development predictor. Moving it onto the trained model
means assembling the same feature vector for scenario cells, and the shared contract
means the map consumers do not change.

---

