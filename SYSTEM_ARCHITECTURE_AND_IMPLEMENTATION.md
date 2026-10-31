# TerraPulse.ai — System Architecture and Implementation

**Target Domain:** AI-Assisted Early Warning and Landslide Risk Monitoring System (SIH26001 — North Eastern Region, India & Nepal Case Study)  
**Document Type:** High-Scale Production System Architecture & Technical Implementation Specification  

---

## 1. Executive Summary & Core Architectural Paradigm

TerraPulse.ai is an enterprise-grade geotechnical monitoring and early warning platform engineered to transition disaster response from **reactive remediation** to **proactive anticipation**. 

The architecture strictly adheres to a **Decoupled Dual-Engine Hazard Assessment Strategy**:
1. **Static Susceptibility Assessment (Where is slope vulnerability inherent?):** Evaluated via an offline-trained Machine Learning classifier (LightGBM) using high-resolution static terrain, geological, geomorphological, hydrological, and infrastructure proximity feature sets (41 features).
2. **Dynamic Trigger Assessment (Is failure occurring right now or imminent?):** Evaluated via real-time and near-real-time meteorological ingestion engines tracking antecedent precipitation, burst intensity, and satellite-derived root-zone soil saturation.

The operational hazard surface fuses these two decoupled engines:
$$\text{Operational Risk} = \max(\text{Susceptibility Score}, \text{Dynamic Trigger Score}) \times \text{Interaction Factor}$$

```
+-------------------------------------------------------------------------------------------------------+
|                                          TERRAPULSE.AI ECOSYSTEM                                      |
+-------------------------------------------------------------------------------------------------------+
                                                     |
                   +---------------------------------+---------------------------------+
                   |                                                                   |
                   v                                                                   v
     [ METEOROLOGICAL & IN-SITU ]                                         [ GEOSPATIAL & SATELLITE ]
       - NASA GPM / IMD Gridded Rainfall                                    - SRTM 30m Digital Elevation Model
       - SMAP / ESA CCI Soil Moisture                                       - Bhuvan Geomorphology / Lineaments
       - Open-Meteo 24h Hourly Forecast                                     - OpenStreetMap Highways & Waterways
                   |                                                                   |
                   +---------------------------------+---------------------------------+
                                                     |
                                                     v
                            +-------------------------------------------------+
                            |       7-STAGE ETL & SPATIAL ENGINE PIPELINE     |
                            |   (Rasterio, PyOGRio, GeoPandas, PostGIS 3.6)   |
                            +-------------------------------------------------+
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
                         v                                                       v
        +---------------------------------+                     +---------------------------------+
        |     STAGE 05: ML SUSCEPTIBILITY |                     |   DYNAMIC METEOROLOGICAL ENGINE |
        |   - Model: LightGBM (600 trees) |                     |   - Antecedent Precipitation Index  |
        |   - 41 Static Extracted Features|                     |   - Empirical Rainfall Thresholds   |
        |   - Registry: models/registry   |                     |   - 24-Hour Forecast Stepper        |
        +---------------------------------+                     +---------------------------------+
                         |                                                       |
                         +---------------------------+---------------------------+
                                                     |
                                                     v
                                  +-------------------------------------+
                                  |     FASTAPI CORE SERVICES LAYER     |
                                  |   - Risk Scoring (/api/risk/*)      |
                                  |   - Alert Router & CAP Generator    |
                                  |   - Citizen Verification & Audit    |
                                  |   - SQLite (State) / PostGIS (Geo)  |
                                  +-------------------------------------+
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
                         v                                                       v
        +---------------------------------+                     +---------------------------------+
        |    REACT 18 + VITE FRONTEND     |                     |    MULTI-CHANNEL DISPATCH       |
        |   - MapLibre GL 2D/3D Terrain   |                     |   - CAP-Compliant XML/JSON      |
        |   - Storm Simulator (Isolated)  |                     |   - Cell Broadcast Gateway      |
        |   - HITL Curator Dashboard      |                     |   - Ntfy WebPush / Mobile Alert |
        |   - Citizen Reporting Portal    |                     |   - Regionalization (EN/HI/NE)  |
        +---------------------------------+                     +---------------------------------+
```

---

## 2. Multi-Tier System Architecture

The TerraPulse ecosystem is structured into four loosely coupled, highly cohesive functional tiers:

### Tier 1: Geospatial Ingestion & Feature Engineering Pipeline (`pipeline.py`)
Executes an automated 7-stage data refinement lifecycle:
- **Stage 01 — Raw Ingestion (`satellite_ingest.py`):** Ingests GSI historical landslide polygons, SRTM 30m DEM tiles, OSM highway/waterway vectors, and Bhuvan thematic datasets.
- **Stage 02 — Coordinate Alignment & CRS Normalization:** Standardizes multi-source geometries onto uniform EPSG:4326 (WGS 84) coordinate references using `pyogrio` and `shapely`.
- **Stage 03 — Hydrological & Topographical Derivations:** Calculates secondary raster matrices including Slope, Aspect, Topographic Wetness Index (TWI), Plan/Profile Curvature, and Distance-to-Fault / Distance-to-Drainage corridors.
- **Stage 04 — Vector Feature Matrix Extraction:** Intersects coordinates against raster and vector stacks, producing 41 high-fidelity features per observation.
- **Stage 05 — Model Inference Engine:** Evaluates susceptibility using the validated LightGBM pipeline.
- **Stage 06 — Operational Risk Scoring:** Combines susceptibility with live antecedent precipitation and saturation indices.
- **Stage 07 — Risk Map Surface Delivery:** Publishes vector geometries and severity classifications to spatial caching layers and API endpoints.

### Tier 2: Backend Core Services (`apps/terrapulse/backend/`)
Built with **FastAPI (Python 3.12)**:
- **`main.py`:** Core API router exposing risk inference, scenario simulation, field verification, warnings, and system status endpoints.
- **`risk/predictor.py`:** Standardized predictor interfaces housing both:
  - `TrainedMLRiskPredictor`: Consumes full 41-feature static vectors into LightGBM for true susceptibility ranking.
  - `DevelopmentRiskPredictor`: Deterministic meteorological heuristic powering parametric scenario sandboxing ("Storm Simulator").
- **`spatial_db.py`:** PostgreSQL 16 + PostGIS 3.6 spatial connector for high-throughput spatial indexing, buffer searches, and distance-to-infrastructure queries.
- **`verification/` (`repository.py`, `service.py`):** Transactional state storage managing crowdsourced citizen reports, field officer observations, and curator audit trails via SQLite.
- **`alerts/cell_broadcast.py`:** Common Alerting Protocol (CAP 1.2) serialization engine with automated fallback gateways (`NtfyCellBroadcastGateway`).

### Tier 3: Frontend Client Application (`apps/terrapulse/frontend/`)
A high-performance SPA built with **React 18 + Vite + TypeScript + Tailwind CSS**:
- **Geospatial Visualization Engine (`GeospatialViewer.tsx`):** Powered by **MapLibre GL JS** and MapTiler, providing continuous 2D planimetric and 3D DEM-extruded terrain exploration, dynamic camera fly-to animations, slope-shading overlays, and vector cell rendering.
- **State Isolation Layer:** Strictly partitions Baseline Risk State (`statusData`), Scenario State (`simulationCells`), and Forecast State (`forecastCells`).
- **Human-in-the-Loop Curator Workspace (`CuratorDashboard.tsx`):** Audit-governed UI for administrators to inspect evidence photos, validate coordinate precision, label hazard types, and stage curated points for retraining datasets.
- **What-If Storm Sandbox (`StormSimulator.tsx`):** Interactive environmental parameter controller testing infrastructure resistance under simulated precipitation spikes without corrupting baseline risk maps.

### Tier 4: Storage & Model Storage Layer
- **Relational & State Storage:** SQLite (`terrapulse.db`) for operational state, report lifecycle logs, and audit records.
- **Spatial Vector Database:** PostGIS 3.6 (`terrapulse_geo`, port 5433) storing millions of GSI landslide polygons, road networks, and drainage lines with R-Tree spatial indexing (`GIST`).
- **Artifact Registry (`models/registry.json`):** Version-controlled model weights (`landslide_v0.4/model.pkl`), training metadata, feature definitions (`feature_schema.json`), and metric ledgers.

---

## 3. Data Architecture & Machine Learning Pipeline

### 3.1 Dataset Construction & Ground Truth Sampling
- **Source Inventory:** Geological Survey of India (GSI) National Landslide Susceptibility Mapping (NLSM) database.
- **Case/Control Balance:** 17,092 points (8,546 verified positive failure centroids + 8,546 negative control points).
- **Negative Control Methodology:** Pseudo-absences generated via spatial buffering (minimum distance > 2.5 km from any recorded event, constrained to stable slope angles $< 8^\circ$).
- **Data Leakage Prevention:** Feature extraction pipelines preserve strict separation between spatial coordinates used for evaluation partitioning and topological attributes.

### 3.2 Feature Matrix Specification (41 Normalized Features)

| Feature Category | Features Included | Source / Method |
| :--- | :--- | :--- |
| **Topography** | Elevation, Slope, Aspect (Eastness, Northness), Plan Curvature, Profile Curvature | SRTM 30m Digital Elevation Model |
| **Hydrology** | Topographic Wetness Index (TWI), Stream Power Index (SPI), Distance to River, Drainage Density | Hydrological routing algorithms over SRTM DEM |
| **Geology & Soils** | Soil Texture, Bulk Density, Clay Content, Silt Content, Distance to Fault/Lineament, Lithology Group | Harmonized World Soil Database (HWSD) & Bhuvan Vector Geomorphology |
| **Anthropogenic** | Distance to Roads, Road Functional Class (`road_fclass`), Land Use / Land Cover (LULC) | OpenStreetMap vector transport network & Copernicus Global Land Cover |
| **Climatology** | Annual Mean Rainfall, Monsoon Peak Intensity, Wet-Day Frequency | WorldClim 30-year climatology baseline |

### 3.3 ML Classifier Architecture & Evaluation Metrics
- **Algorithm:** LightGBM Gradient Boosted Decision Trees (600 estimators, 31 leaves, learning rate = 0.05, feature fraction = 0.8).
- **Validation Framework:** 5-fold Spatial Block Cross-Validation (preventing spatial autocorrelation leakage) and Leave-One-State-Out (LOSO) cross-validation across Sikkim, Himachal Pradesh, and Uttarakhand.
- **Evaluation Performance:**
  - **Recall:** 0.89 (Spatial Block CV) / 0.84 (LOSO)
  - **ROC-AUC:** 0.74 (Spatial Block CV) / 0.69 (LOSO)
  - **Inference Latency:** $< 12\text{ ms}$ per vector scoring request.
- **Model Explainability (XAI):** Global TreeSHAP and gain importances mapped into per-cell human-readable contributing factors (e.g., "Slope Angle $> 34^\circ$", "High Topographic Wetness").

---

## 4. Operational API Contracts

The backend exposes a deterministic, documented REST/RPC contract:

### 4.1 Hazard Risk Scoring

#### `POST /api/risk/predict-trained`
Accepts a 41-feature extracted vector and outputs static susceptibility ranking from `landslide_v0.4`.
```json
// Request Payload
{
  "features": {
    "elevation": 1845.2,
    "slope": 36.8,
    "aspect": 142.0,
    "twi": 8.42,
    "soil_clay_pct": 28.5,
    "dist_to_fault": 340.0,
    "dist_to_road": 45.0,
    "road_fclass": "primary"
  }
}

// Response (HTTP 200)
{
  "susceptibility_score": 0.824,
  "risk_level": "HIGH",
  "predictor": "TrainedMLRiskPredictor",
  "model_version": "landslide_v0.4",
  "contributing_factors": [
    {"feature": "slope", "importance": 0.28, "direction": "positive"},
    {"feature": "dist_to_road", "importance": 0.22, "direction": "positive"}
  ]
}
```

#### `POST /api/risk/predict-batch`
Accepts an array of dynamic meteorological inputs for up to 500 spatial monitoring cells (powers the Storm Simulator scenario playback).

### 4.2 Dynamic Environmental & Pipeline Endpoints
- `GET /api/live/conditions`: Fetches live aggregated meteorological data (1h, 24h, antecedent precipitation, soil moisture).
- `GET /api/live/risk`: Returns the current cycle's scored spatial monitoring cells.
- `GET /api/spatial/cells-near-landslides?metres=25000`: Queries PostGIS for spatial proximity between active infrastructure corridors and historical failure clusters.
- `GET /api/pipeline/stages`: Reports health, latency, and status for each of the 7 pipeline phases.

### 4.3 Human-in-the-Loop & Alerting Endpoints
- `POST /api/verification/submit`: Crowdsourced or field-officer incident ingestion.
- `GET /api/verification/pending`: Curator triage queue listing unverified incidents.
- `POST /api/verification/review`: Curator action (`approve`, `reject`, `needs_evidence`, `supersede`).
- `POST /api/alerts/broadcast/dispatch`: Generates and routes CAP 1.2 emergency alerts across registered broadcast gateways.

---

## 5. Early Warning & Multi-Channel Cell Broadcast System

```
       [ High / Critical Warning Triggered ]
                         |
                         v
       [ CAP 1.2 Protocol Construction Engine ]
                         |
      +------------------+------------------+
      |                  |                  |
      v                  v                  v
  [English]           [Hindi]            [Nepali]
      |                  |                  |
      +------------------+------------------+
                         |
                         v
           [ CellBroadcastGateway Interface ]
                         |
             +-----------+-----------+
             |                       |
             v                       v
[ Simulated Telecom Gateway ]   [ Ntfy WebPush / Mobile Gateway ]
 (NDMA/SACHET Compliant XML)     (Instant Android / iOS Alert)
```

1. **CAP 1.2 Serialization:** Converts detected risk thresholds into standardized OASIS Common Alerting Protocol formats specifying polygon bounding vertices, event codes (`GEO-LANDSLIDE`), certainty, and urgency.
2. **Automated Multi-lingual Translation:** Emits synchronized warnings in English, Hindi, and Nepali tailored for NER/Sikkim communities and field operators.
3. **Gateway Abstraction (`CellBroadcastGateway`):** Decouples alert generation from downstream hardware delivery. The production system supports both simulated cellular tower broadcasts and live mobile notifications via encrypted push channels (`ntfy.sh`).

---

## 6. Security, Resilience, & Verification Rules

1. **Zero State Pollution Rule:**
   - The interactive Storm Simulator executes entirely in an isolated React state buffer (`simulationCells`). It is strictly prohibited from mutating production Risk Map baselines (`statusData`).
2. **Human-in-the-Loop Training Gate:**
   - No crowdsourced or citizen field report enters the training matrix automatically. Reports must traverse the Curator lifecycle (`pending_review` $\rightarrow$ `approved` $\rightarrow$ `staged_buffer` $\rightarrow$ `offline_retrain_pipeline`).
3. **Failure Containment & Graceful Degradation:**
   - If PostgreSQL/PostGIS connectivity drops, the system falls back to cached SQLite spatial centroids without breaking client-side UI rendering.
   - If live satellite telemetry times out, the hazard engine operates on the latest valid WorldClim and IMD climatology baselines, marking data freshness headers accordingly.

---

## 7. Technology Stack Reference

| Tier | Component | Technology / Library |
| :--- | :--- | :--- |
| **Frontend** | Framework & Build | React 18, TypeScript, Vite |
| | UI Components | Tailwind CSS, Lucide Icons, Shadcn UI primitives |
| | Geospatial Visuals | MapLibre GL JS, MapTiler 3D Terrain, WebGL |
| **Backend** | Runtime & API | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| | Scientific Computing | NumPy, Pandas, Scikit-Learn, LightGBM |
| | Spatial Geometry | GeoPandas, Shapely, PyOGRio, Rasterio |
| **Databases** | Operational Relational | SQLite 3 |
| | Spatial Vector Store | PostgreSQL 16 + PostGIS 3.6 (port 5433) |
| **Deployment**| Orchestration | Docker containerization, Render Cloud hosting |

