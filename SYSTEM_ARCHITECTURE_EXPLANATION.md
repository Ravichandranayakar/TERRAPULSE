# TerraPulse.ai — System Architecture & Implementation Guide

**Project:** TerraPulse.ai (SIH26001 — AI-Based Early Warning & Landslide Risk Monitoring)  
**Document Purpose:** Complete Architecture Reference, Mermaid Flowcharts, Evaluator Explanations, and Defense Script.  
**Architecture Diagram Image:** [`model_graphs/system_architecture_diagram.png`](model_graphs/system_architecture_diagram.png)

---

## 1. Visual System Architecture Diagram (Mermaid)

```mermaid
flowchart TD
  subgraph SOURCES["1. DATA SOURCES"]
    direction LR
    S1["Meteorological In-Situ Data<br/>• NASA GPM & IMD Rainfall<br/>• SMAP / ESA Soil Moisture<br/>• Open-Meteo 24h Forecast"]
    S2["Geospatial & Satellite Data<br/>• SRTM 30m Elevation DEM<br/>• Bhuvan Geomorphology<br/>• OpenStreetMap Roads & Rivers"]
  end

  subgraph PIPELINE["2. 7-STAGE ETL & SPATIAL ENGINE"]
    direction TB
    P1["Raw Ingestion & Reprojection to EPSG:4326"]
    P2["Spatial Derivatives: Slope, Aspect, TWI, Distances"]
    P3["Feature Matrix Assembly: 41 Standardized Attributes"]
    P1 --> P2 --> P3
  end

  subgraph DUAL_ENGINE["3. DUAL-ENGINE HAZARD ASSESSMENT"]
    direction LR
    subgraph ENGINE_STATIC["Static Susceptibility Engine (WHERE?)"]
      M1["LightGBM ML Model<br/>600 Trees · 41 Features"]
      R1["Static Susceptibility Score<br/>Natural Ground Vulnerability"]
      M1 --> R1
    end

    subgraph ENGINE_DYNAMIC["Dynamic Meteorological Engine (WHEN?)"]
      M2["Rainfall Thresholds &<br/>Antecedent Soil Saturation"]
      R2["Dynamic Trigger Score<br/>Real-Time Weather Threat"]
      M2 --> R2
    end
  end

  FUSION["OPERATIONAL RISK FUSION<br/>Combines Static Vulnerability + Dynamic Trigger"]

  subgraph BACKEND["4. FASTAPI CORE BACKEND & STORAGE"]
    direction TB
    API["FastAPI Application Services<br/>Risk Scoring · Alert Routing · Verification Audits"]
    DB_SQLITE[("SQLite Database<br/>Incident Reports & Audit State")]
    DB_POSTGIS[("PostGIS 3.6 Cluster<br/>Spatial Roads & Geo Polygons")]
    MODEL_REG[("Model Registry<br/>landslide_v0.4 Artifacts")]
    API <--> DB_SQLITE
    API <--> DB_POSTGIS
    API <--> MODEL_REG
  end

  subgraph OUTPUTS["5. USER INTERFACE & DISPATCH TIER"]
    direction LR
    subgraph FRONTEND["React 18 + Vite Dashboard"]
      UI1["MapLibre 2D / 3D Terrain Viewer"]
      UI2["Storm Simulator Scenario Sandbox"]
      UI3["Citizen Incident Portal"]
      UI4["Curator Verification Workspace"]
    end

    subgraph DISPATCH["Multi-Channel Dispatch"]
      D1["CAP 1.2 Alert Engine<br/>English · Hindi · Nepali"]
      D2["Simulated Cell Broadcast<br/>CAP / Telecom XML"]
      D3["Live Mobile Push<br/>ntfy.sh WebPush Alerts"]
      D1 --> D2
      D1 --> D3
    end
  end

  subgraph HITL["6. HUMAN-IN-THE-LOOP (HITL) FEEDBACK"]
    direction LR
    C1["Citizen / Field Photos"] --> C2["Curator Review: Approve / Reject"] --> C3["Curated Training Buffer"] --> C4["Gated Offline Retraining"]
  end

  SOURCES --> PIPELINE
  P3 --> M1
  S1 --> M2
  R1 --> FUSION
  R2 --> FUSION
  FUSION --> API
  API --> FRONTEND
  API --> D1
  UI3 --> C1
  C4 -.-> MODEL_REG
```

---

## 2. Simple Explanation: Susceptibility vs. Dynamic Engine

If your madam or jury asks: **"What is the difference between Susceptibility and the Dynamic Meteorological Engine?"**

Explain it with this real-world gun analogy:

| Feature | Static Susceptibility Engine | Dynamic Meteorological Engine |
| :--- | :--- | :--- |
| **Real Meaning** | **Natural Vulnerability** of the land. | **Immediate Weather Trigger** happening now. |
| **Simple Analogy** | The **Loaded Gun** (it is inherently dangerous, even if unfired). | **Pulling the Trigger** (the action that causes the shot). |
| **Does it change?**| **No.** It stays constant week to week (slope angle, rock type, distance from road). | **Yes.** Changes hour by hour (rainfall intensity, accumulated rain, soil moisture). |
| **Input Data** | SRTM DEM (slope, elevation, TWI), soil composition, distance to fault line, road cutting. | 1h/24h rainfall, antecedent 3-day rainfall, SMAP soil saturation, weather forecast. |
| **Core Technology**| **Trained LightGBM Machine Learning Model** (41 features). | **Empirical Rainfall Thresholds & Antecedent Saturation Logic**. |
| **Question Answered**| **"WHERE is the ground naturally prone to collapsing?"** | **"IS the current weather dangerous enough to cause a failure right now?"** |

### Operational Risk Fusion:
* A flat playground with heavy rainfall will not slide.
* A steep, unstable cliff on a dry sunny winter day will not slide.
* **A landslide only occurs when the land is naturally vulnerable (High Susceptibility) AND heavy rain arrives (High Dynamic Trigger).** TerraPulse fuses both to calculate the actual operational risk:
$$R_{\text{op}} = \min(1.0, \, \max(S_{\text{static}}, T_{\text{dynamic}}) \cdot [1 + \alpha \cdot S \cdot T])$$

---

## 3. Simple Explanation: What is Multi-Channel Dispatch?

If they ask: **"What is Multi-Channel Dispatch and how does it work?"**

**Answer in 4 simple points:**
1. **Definition:** When high or critical risk is detected, the system cannot rely on only one communication method. Multi-channel dispatch means broadcasting emergency warnings through multiple networks simultaneously so everyone receives it.
2. **Standard Protocol (CAP 1.2):** We format all alerts into **Common Alerting Protocol (CAP 1.2)** — the international XML/JSON emergency standard used by disaster authorities (like NDMA / SACHET).
3. **Trilingual Localization:** The alert message is automatically prepared in:
   * **English** (for administrative officers and state disaster teams).
   * **Hindi** (for national disaster relief forces).
   * **Nepali** (for local hill communities and transport drivers along the Sikkim / Nepal corridor).
4. **The Channels Deployed:**
   * **Cell Broadcast (Simulated):** Formats geo-fenced cell tower alert payloads ready for telecom integration without needing internet connectivity.
   * **Mobile Push Notification (ntfy.sh):** Sends instant real-time emergency notifications directly to smartphones and field tablets during live operations.

---

## 4. 60-Second Speech for Your Presentation

> *"Respected Madam and evaluators, TerraPulse AI solves the landslide problem by decoupling **where** the ground is dangerous from **when** it will fail.*
> 
> *Our **Static Susceptibility Engine** uses a trained **LightGBM model with 41 terrain and geological features** to evaluate the inherent vulnerability of the slope.*
> 
> *Our **Dynamic Meteorological Engine** continuously monitors live rainfall, 24-hour forecasts, and soil saturation to detect active failure triggers.*
> 
> *When both align, our **FastAPI backend** fuses the scores, plots the risk in real-time on our **MapLibre 3D terrain**, and triggers **Multi-Channel CAP 1.2 alerts** in English, Hindi, and Nepali via Cell Broadcast and mobile push.*
> 
> *Finally, crowdsourced citizen reports pass through our **Human-in-the-Loop Curator** to ensure verified ground evidence feeds safe, offline model retraining."*

