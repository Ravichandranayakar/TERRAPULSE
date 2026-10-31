# TerraPulse.ai - Complete Project PRD

**Plain-English guide to every feature, every file and every function.**

SIH 2026 Problem Statement **SIH26001** - AI-Based Early Warning and Landslide Risk
Monitoring System for the North Eastern Region (NER).

Live demo: https://terrapulse-86te.onrender.com/

---

## How to read this document

This is written so that anyone - a judge, a teammate, or you three months from now -
can understand the whole system without reading the code first.

- **Section 1** is the story of the project in one page.
- **Section 2** is the demo script: what to show, in what order, and what to say.
- **Section 3** onwards goes deep, layer by layer.
- **Section 12** lists what the system does NOT do yet. Read it before the demo so
  nothing surprises you.
- **Section 13** is the jury question bank with ready answers.

Every number in this document was read off the running system, not estimated.

---

## 1. The project in one page

### 1.1 The problem

The North Eastern Region of India loses roads, bridges and villages to landslides
every monsoon. Today the response is **reactive**: someone sees a slope fail, reports
it, and help is sent afterwards. Nobody is watching the slopes that are *about to*
fail.

The problem statement asks for a system that:

| # | Requirement | What TerraPulse built |
|---|---|---|
| a | Collect and analyse rainfall, soil moisture, satellite imagery, terrain and historical records | 7-stage pipeline using 10 real public datasets |
| b | Use AI/ML to find high-risk zones and predict events | LightGBM susceptibility model over 17,092 real labelled points |
| c | Real-time alerts to district administrations and communities | Automated alert engine plus multilingual cell broadcast |
| d | GIS mapping of vulnerable roads, villages and infrastructure | MapLibre 2D/3D map with NH-10 corridor and exposure layers |
| e | Citizens and field officers upload geo-tagged photos | Citizen Portal feeding a curator who approves or rejects reports |
| f | Dashboards for severity, connectivity, forecast and response priority | Five dashboard views plus a 24-hour forecast scrubber |
| g | Multilingual, low-network and offline support | English, Hindi, Nepali alerts; model is 2 MB so it fits offline deployment |

### 1.2 What makes it work

There are two completely different jobs in this system, and mixing them up is the
single most common mistake. TerraPulse keeps them apart on purpose.

**Job 1 - Susceptibility: "how dangerous is this place?"**

Some things about a hillside never change hour to hour: how steep it is, what rock
and soil it is made of, how far it sits from a road, how much rain it gets in a
normal year. These describe the *place*. The trained model reads these and gives
each spot a danger ranking.

**Job 2 - Trigger: "is it happening right now?"**

Rainfall and soil moisture *do* change, every hour. A separate, clearly-labelled
trigger layer watches the live measurements and raises the alarm when they cross the
levels recorded against real historical landslides.

**The alert shown on the map is the higher of the two.** A place can be highly
susceptible and currently quiet - that is a yellow zone, not a red one. A place
becomes red when the ground is dangerous *and* the rain is arriving.

> **One-line answer if a judge asks what the AI does:**
> "The model ranks how dangerous each slope is. A separate live layer watches the
> rain. The map shows the more urgent of the two, and escalates when both are high."

### 1.3 The honest boundaries

Stated up front, because a judge will ask and a confident wrong answer is worse than
a clear limit:

- The model is trained on a **1:1 case/control sample**. Its output is a **ranking,
  not a calibrated probability**. A score of 0.8 does not mean "80% chance".
- Negatives are **generated**, not observed. Nobody records "a landslide did not
  happen here". They are placed at verified non-landslide locations, away from
  recorded events.
- Only **10 monitoring cells** are live, all in Sikkim. The model is national-scale;
  the live map is a demonstration corridor.
- **Retraining is not real-time.** It is a separate offline job with a safety gate.

---

## 2. The demo script

Run the demo in this order. Each step builds on the previous one.

### Step 0 - before anyone walks in

```bash
cd apps/terrapulse/backend
uvicorn main:app --reload --port 5000
```
```bash
cd apps/terrapulse/frontend
npm run dev
```

Open http://localhost:5173/ and confirm the top strip shows **10 monitored zones**
and a **Model Status** card reading `LightGBM` with `landslide_v0.4`.

### Step 1 - Risk Map (the default view)

**Say:** "This is the live map. Ten monitoring cells along the NH-10 corridor in
Sikkim. Every cell has been scored by our trained LightGBM model from real terrain,
soil, land cover, distance and geology data - 41 features per cell, no hand-typed
values."

**Click a cell.** The XAI panel opens showing which features drove that score.

**Say:** "This is the explainability panel. It tells you *why* the model scored this
cell the way it did, ranked by how much the model relies on each feature."

### Step 2 - 24-hour Forecast

**Say:** "Same corridor, next 24 hours. The blue chart is real hourly rainfall from
Open-Meteo. Drag the time scrubber and the map recolours."

### Step 3 - Storm Simulator

**Say:** "This replays a severe monsoon scenario hour by hour so we can show what a
district office would see before an event, not after."

**Be precise here:** the simulator runs on the development risk contract, not the
trained model. See section 11.3.

### Step 4 - Early Warnings, then Cell Broadcast

Open a warning, then open the cell broadcast modal.

**Say:** "The alert goes out in English, Hindi and Nepali, with the affected
infrastructure named - because a warning nobody can read is not a warning."

### Step 5 - Citizen Portal

Switch to Citizen mode using the mode menu. File a report with a photo and GPS.
Switch back to Authority mode.

**Say:** "A photo from a field officer or a citizen becomes a map marker
immediately. It does not become training data until a curator reviews it."

### Step 6 - Curator

Open the Curator view and approve the report.

**Say:** "This is the human in the loop. Approved reports become training rows for
the next model version. Nothing reaches the model unless a person signed off."

---

## 3. Glossary - the words the jury will use

| Term | Plain meaning |
|---|---|
| **Susceptibility** | How dangerous a place is because of its terrain. Does not change hourly. |
| **Trigger** | The live event that sets a landslide off - usually rain. Changes hourly. |
| **Feature** | One measured number fed to the model, e.g. slope in degrees. |
| **Label** | The answer the model learns. 1 = landslide happened, 0 = it did not. |
| **Positive / Negative sample** | A real landslide location / a verified non-landslide location. |
| **Climatology** | The long-term average pattern of rainfall, not today's weather. |
| **Antecedent rainfall** | Rain that fell over the previous days. Wet ground fails more easily. |
| **Block cross-validation** | Splitting data by geography, not randomly, so the model is tested on places it has never seen. |
| **Leave-one-state-out (LOSO)** | Train on every state except one, test on the state left out. The strictest test we run. |
| **ROC-AUC** | How well the model ranks a real landslide above a non-landslide. 0.5 = random, 1.0 = perfect. |
| **Recall** | Of all the real landslides, how many did we catch. This is the safety-critical number. |
| **Precision** | Of all our alarms, how many were real. This is the "false alarm" number. |
| **F1** | One number balancing precision and recall. |
| **Threshold** | The score above which we raise an alert. A policy dial, not a model property. |
| **PostGIS** | A database that understands geography, so it can answer "which cells are within 25 km of a landslide". |
| **STAC** | A public index that finds satellite scenes. It is the catalogue, not the data. |
| **COG** | Cloud-Optimised GeoTIFF - a satellite image a program can read in small pieces over the internet. |

---

## 4. The data layer - every dataset, and why it is here

All raw data lives in `TERRAPULSE_DATA/`. The folder numbers are the order the data
moves through the pipeline. **Nothing in the model is a hand-typed number.** Every
value is computed from one of these files at the exact coordinate being scored.

### 4.1 The table

| Folder | Dataset | Who publishes it | What it gives the model |
|---|---|---|---|
| `01_LANDSLIDE_LABELS` | GSI Bhu-Sanket Landslide Inventory | Geological Survey of India | **The answers.** 8,546 real recorded landslides - the positive labels |
| `01_LANDSLIDE_LABELS/8169506` | Southern Sikkim inventory (2002-2019) | Zenodo / BGS | Extra polygons, event years, geology context |
| `01_LANDSLIDE_LABELS` | Raigad dataset | Mendeley | Reference only, not NER training data |
| `04_RAINFALL/IMD_RF25` | IMD gridded rainfall 0.25 deg | India Meteorological Department | Rainfall **climatology**: annual, monsoon, wettest 1-day and 5-day totals. 35 files, 1991-2025 |
| `05_TERRAIN/Copernicus_DEM` | Copernicus DEM GLO-30 | ESA / Copernicus | Elevation, slope, aspect, curvature, terrain ruggedness. 99 tiles, 4.24 GB |
| `06_SOIL/SoilGrids` | SoilGrids 0-5 cm | ISRIC | Clay, sand, silt, bulk density, organic carbon, nitrogen |
| `07_GEOLOGY/Bhuvan` | Bhuvan geomorphology + lineaments | ISRO / NRSC | Landform type and distance to faults/fractures |
| `07_GEOLOGY/GSI` | GSI geology for NER | Geological Survey of India | Held on disk, **not yet a model feature** |
| `08_LANDCOVER` | ESA WorldCover 2021 v200 | ESA | Land-cover class plus tree/shrub/grass/crop/built/bare/snow/water shares. 12 tiles, 998 MB |
| `09_INFRASTRUCTURE/OSM` | OpenStreetMap India | OSM / Geofabrik | Distance to nearest road, river and water body |
| `10_SATELLITE` | Sentinel-1 / Sentinel-2 | Copernicus | Live imagery pulled on demand. **Not a model input** - see 4.4 |
| `11_NEPAL_CASE_STUDY` | Nepal 2026 flood + 2015 landslides | HOT / UNOSAT / ICIMOD | Second region for the case-study mode |
| `13_MODEL_DATASETS` | Training tables | Built by our scripts | The assembled model-ready files |

### 4.2 Why each one is needed

**Terrain (DEM) - why:** landslides happen on slopes. Steepness is the single most
important physical fact about a hillside. The DEM also gives us *curvature* (whether
the slope is hollow or bulging - hollows collect water) and *aspect* (which way it
faces, which controls how wet and how vegetated it stays).

**Rainfall (IMD) - why:** water is what actually pushes a slope over the edge. An
area that normally receives 2,600 mm a year is pre-conditioned differently from one
receiving 800 mm. We use the long-term pattern here, not today's rain, because this
is the susceptibility model.

**Soil (SoilGrids) - why:** sandy soil drains; clay holds water and gets heavy;
organic content changes how much water the soil can absorb before it gives way.

**Land cover (ESA WorldCover) - why:** tree roots hold a slope together. Bare ground
or cropland does not. This is also where we capture the human factor - built-up
surfaces and cleared slopes.

**Distance to roads, rivers, water (OSM) - why:** road cutting undercuts a slope and
loads it with water runoff. Rivers erode the toe of a slope. Both are standard
features in published landslide literature.

**Geomorphology and lineaments (Bhuvan) - why:** this is the *geology* answer. A
lineament is a fracture or fault in the rock - a weak seam. Landslide studies
worldwide use distance-to-lineament as a predictor. It is also authoritative Indian
data (ISRO/GSI at 1:50,000), which matters when defending the choice to a judge.

**Landslide labels (GSI) - why:** without recorded events there is nothing to learn
from. GSI is the official national inventory.

### 4.3 The training tables

Built by our scripts from the sources above:

| File | Shape | What it is |
|---|---|---|
| `landslide_dataset_v0.1.csv` | 17,092 x 56 | The base table. 8,546 real landslides + 8,546 generated non-landslide points |
| `landslide_dataset_v0.2_bhuvan.csv` | 17,092 x 65 | v0.1 **plus 9 Bhuvan geology columns**. This is what the shipped model reads |
| `landslide_dataset_landslide_v0.4.csv` | 17,093 x 56 | Produced by the feedback loop: v0.1 plus the first curator-approved report |

**How the negatives were made.** Nobody records where a landslide *did not* happen,
so they have to be constructed. `scripts/build_negatives.py` places points away from
recorded landslides, then each candidate is checked for low slope and for distance
from known events. This is a standard approach and it is disclosed everywhere the
dataset is described.

**The full audit trail** for the base table is in
`landslide_dataset_v0.1_audit.txt` - row counts, drop reasons, class balance. If a
judge asks "how do I know you did not fudge the data", that file is the answer.

### 4.4 A deliberate exclusion: satellite imagery

Sentinel-1 and Sentinel-2 are downloaded and displayed, but they are **not fed to
the model**. This is a choice, not an oversight.

- The model's 41 features are a fixed contract. Adding an image band means retraining
  and revalidating everything.
- Optical imagery is useless during the event that matters - landslides happen in
  heavy cloud and rain, which is exactly when Sentinel-2 sees nothing.
- So satellite imagery is presented as a **live observation layer** next to the score,
  never folded into it.

> **Jury answer:** "Satellite imagery is an observation layer, not a model input. We
> show it beside the score because the model's feature contract is fixed and
> validated. Folding an image band in means a full retrain and revalidation, which is
> the correct next step, not something to slip in quietly."

---

## 5. The pipeline - seven stages, start to finish

The whole operational path lives in one file:
`apps/terrapulse/backend/pipeline.py`

```
01 DATA INGESTION      collect raw data from APIs, rasters, CSV, GeoJSON, Shapefile
02 DATA PREPROCESSING  clean, fill gaps, scale, align to the same grid
03 GEO PROCESSING      derive slope/aspect/curvature, grid and reproject
04 FEATURE ENGINEERING build the feature matrix - spatial + temporal
05 AI / ML MODEL       load the trained model and run inference
06 RISK ENGINE         turn scores into 0-100 and LOW/MODERATE/HIGH/CRITICAL
07 SERVE & VISUALIZE   FastAPI, PostGIS, React map, alerts
        |
        v
   FEEDBACK LOOP       events -> curator -> curated dataset -> retrain -> validate
                       -> new version -> better predictions

   RUNTIME INFERENCE   live data -> features -> loaded model -> risk map
```

### How to run it

| Command | What it does |
|---|---|
| `python pipeline.py` | Full run, human-readable |
| `python pipeline.py --json` | Machine-readable, for the API |
| `python pipeline.py --stages 01,04` | Just the stages you name |
| `python pipeline.py --live` | Only the runtime inference path |
| `python pipeline.py --feedback` | Check or run the retraining cycle |

### 5.1 Stage 01 - Data ingestion

**What it does, simply:** goes and gets the raw material, and reports what it found.

Function: `stage_01_ingestion(with_satellite)`

It checks each source and records: how many files are present, the newest Sentinel-1
and Sentinel-2 scene, how many cells have a scene available, and which variables came
from where. If a source is missing it is reported, not hidden.

Returned fields: `sources`, `files`, `terrain_dem`, `soil`, `landcover`,
`rainfall_imd`, `landslide_labels`, `s2_cells_with_scene`, `s1_cells_with_scene`, `present`.

### 5.2 Stage 02 - Data preprocessing

**What it does, simply:** tidies the raw tables and reports on data quality.

Function: `stage_02_preprocessing()`

Counts rows, positives, negatives, duplicate rows and missing cells in the training
table, so every later claim about the data has a source. Returned fields: `rows`,
`positives`, `negatives`, `duplicate_rows`, `missing_cells`, `columns`.

### 5.3 Stage 03 - Geo processing

**What it does, simply:** turns a flat height map into the slope facts a model can use.

Functions: `stage_03_geo(refresh)`, `_rebuild_cell_features()`, `_source_staleness()`

For each monitoring cell it computes, from the Copernicus DEM at that coordinate:

- `elevation_m` - height above sea level
- `slope_deg` - steepness in degrees
- `curvature_1pm` - hollow or bulge
- `tri_m` - terrain ruggedness index, how broken the ground is
- `aspect` - compass direction the slope faces
- `dem_tile` - which source tile it came from (provenance)

`_source_staleness()` checks how old each source file is, and
`_rebuild_cell_features()` regenerates the cell feature cache when a source is
republished. That is why the map cannot silently drift from the data.

### 5.4 Stage 04 - Feature engineering

**What it does, simply:** assembles the final list of numbers the model reads.

Function: `stage_04_features()`

Two kinds of features are combined:

**Spatial (do not change hour to hour):** elevation, slope, aspect, curvature,
ruggedness, land cover, soil texture, distance to roads and rivers, geomorphology,
lineament distance.

**Temporal (change every hour):** antecedent rainfall over 1 hour, 24 hours, 3 days
and 7 days, plus soil moisture.

The result is a **feature matrix** - one row per location, one column per feature.
For the live cells this is 41 columns, verified by the test suite.

### 5.5 Stage 05 - AI / ML model

**What it does, simply:** loads the saved model. It does **not** train one.

Function: `stage_05_model()`

Reads the registry to find which version is active, loads that artifact, and reports
its measured leave-one-state-out metrics. Returned fields: `active_version`,
`algorithm`, `artifact_dir`, `feature_count`, `alert_cut`, `metrics_loso`,
`registry_versions`.

> **This is important to say out loud in the demo.** The operational path never
> trains. Training is a separate offline job. If a judge asks "is your model
> learning live", the answer is no, and that is correct engineering - a model that
> updates itself mid-operation cannot be validated.

### 5.6 Stage 06 - Risk engine

**What it does, simply:** turns a raw score into something a human can act on.

Function: `stage_06_risk_engine()`

The model returns a number between 0 and 1. That is not useful to a district officer.
So the stage produces:

- **Probability** - the raw 0-1 model score
- **Risk score** - the same value scaled to 0-100
- **Risk class** - LOW / MODERATE / HIGH / CRITICAL

It also combines the two components described in section 1.2. Returned fields:
`components` (susceptibility, trigger, combination), `alert_distribution`,
`cells_scored`, `inference_ms_per_cycle`.

### 5.7 Stage 07 - Serve and visualize

**What it does, simply:** stores the result where the map can read it, and hands it
to the website.

Function: `stage_07_serve(store)`

- **FastAPI** serves the REST API and the RPC bridge the frontend calls
- **SQLite** keeps application state (cells, predictions, warnings, reports)
- **PostGIS** answers spatial questions the database can do better than Python
- **React + MapLibre GL** draws the map

Measured on the last full run: 10 cells written, 7 historical landslides written,
10 observations written, and the spatial query returned *11 cells within 25 km of a
recorded landslide*.

### 5.8 The runtime inference path

**What it does, simply:** the loop that runs by itself, forever.

Function: `runtime_inference_path()`

```
live data -> features -> loaded trained model -> risk map / alert
```

This is what the scheduler calls every 15 minutes. It reports `model_status`,
`cells_live`, `cells_total` and `total_ms`.

---

## 6. The model

### 6.1 What it is

**Shipped model: LightGBM, artifact `landslide_v0.4`.**

LightGBM is a *gradient-boosted decision tree* model. In plain words: it builds many
small decision trees one after another, where each new tree tries to fix the mistakes
of the ones before it. It is fast, small, and works well on tables of numbers -
exactly our situation.

The other three models were trained on the identical data with identical folds so the
comparison is fair. All four are recorded in `models/landslide_v0.4/metrics.json`.

### 6.2 How it was trained

| | |
|---|---|
| Script | `scripts/train_landslide_model.py` |
| Dataset | `landslide_dataset_v0.2_bhuvan.csv` |
| Rows | 17,092 (8,546 landslide, 8,546 non-landslide) |
| Features | 41 |
| Validation | 5-fold block cross-validation **and** leave-one-state-out |
| Splitting | By geographic block, not randomly |
| Artifact size | 2.1 MB |

**Why block cross-validation matters.** If you split randomly, two points 50 metres
apart can end up on opposite sides of the split. The model then "recognises" the test
set instead of generalising. Splitting by geographic block means the model is always
tested on ground it has genuinely never seen. This is the difference between a
believable score and a fake one.

### 6.3 Measured results

Averages across folds. Read off `metrics.json`, not estimated.

| Algorithm | Block CV ROC-AUC | Block CV F1 | Leave-one-state-out ROC-AUC | Leave-one-state-out F1 |
|---|---|---|---|---|
| Logistic Regression | 0.6689 | 0.6937 | 0.6240 | 0.6313 |
| Random Forest | 0.7354 | 0.7070 | 0.6781 | 0.6661 |
| XGBoost | **0.7424** | 0.7186 | **0.6875** | 0.6656 |
| **LightGBM (shipped)** | 0.7389 | **0.7200** | 0.6863 | **0.6659** |

### 6.4 How to explain choosing LightGBM without overclaiming

**Do not say** "LightGBM is the best model." That is not what the numbers show, and
an informed judge can pick it apart.

XGBoost has a marginally higher ROC-AUC; LightGBM has a marginally higher F1. The
gaps are inside the fold-to-fold noise. So the truthful sentence is:

> **"LightGBM combined with the Bhuvan geology layers is our best measured
> combination. The tree models are statistically tied; we chose LightGBM because it
> also gave the best catch rate on an unseen state and its artifact is 2 MB, which
> fits an offline deployment."**

**Two supporting facts worth having ready:**

- **Per-state catch rate (recall) for LightGBM on a state it has never seen:**
  Arunachal Pradesh 0.93, Assam 0.84, Manipur 0.83, Meghalaya 0.82, Mizoram 0.98,
  Nagaland 0.88, Sikkim 0.65, Tripura 0.81. Average **0.84**.
- **Size.** The model is **2.1 MB**. That is small enough to run on a laptop in a
  district office with no internet, which is the point of the offline requirement.

### 6.5 The alert bands, and why they are where they are

Taken from `risk/trained_predictor.py`, anchored on measured operating points:

| Score | Class | What it means | Measured behaviour |
|---|---|---|---|
| >= 0.69 | **CRITICAL** | Extreme | Precision 0.75 - three of four warnings are real |
| >= 0.28 | **HIGH** | Dangerous | Recall 0.80 - catches four of five real landslides |
| >= 0.10 | **MODERATE** | Watch | Recall 0.95 - catches nineteen of twenty |
| < 0.10 | **LOW** | Quiet | - |

**These are operational bands, not validated severity classes.** They were chosen by
measuring what each cut-off actually catches. The full trade-off table comes from
`scripts/model_operating_points.py`.

> **The dial answer.** If a judge asks "what if you want to catch more landslides",
> the answer is: lower the threshold. Lowering it raises recall and raises false
> alarms. That is a *policy* decision for the district administration, not a model
> limitation - and we can produce the exact cost table for any cut-off they name.

### 6.6 Where the model files live

| Path | What |
|---|---|
| `models/registry.json` | Which version is active, and why it was promoted |
| `models/landslide_v0.4/lgbm.joblib` | The trained model itself (2.1 MB) |
| `models/landslide_v0.4/feature_schema.json` | The 41 feature names, their order, and which may be blank |
| `models/landslide_v0.4/thresholds.json` | The alert cut-offs |
| `models/landslide_v0.4/metrics.json` | The measured scores in the table above |
| `models/landslide_v0.4/training_report.txt` | Full human-readable training log |
| `models/landslide_v0.4/oof_predictions.csv` | Every held-out prediction, so anyone can re-check the numbers |

`oof_predictions.csv` is worth mentioning to judges: it is the raw evidence behind
every metric. We are not asking anyone to take the scores on trust.

---

## 7. The live cycle - how the map updates by itself

File: `apps/terrapulse/backend/live_pipeline.py`

### 7.1 The two components, again - because this is the core idea

| | Susceptibility | Trigger |
|---|---|---|
| Question it answers | How bad would it be here? | Is it happening now? |
| Computed from | Terrain, soil, land cover, distance, geology, rainfall climatology | Live rainfall and soil moisture |
| Changes | Never, hour to hour | Every cycle |
| Produced by | The trained LightGBM model | `classify_trigger()` thresholds |
| Output | LOW / MODERATE / HIGH / CRITICAL | NONE / WATCH / ALERT / SEVERE |

### 7.2 The trigger thresholds

From `live_pipeline.py`:

```python
TRIGGER_ALERT = {
    "rainfall_24h_mm": 100.0,
    "rainfall_3d_mm":  200.0,
    "rainfall_7d_mm":  180.0,
}
```

These are not invented round numbers. They are derived from the recorded rainfall
conditions of the historical landslide events in our own inventory.

Function `classify_trigger(cond)` turns a measurement into a level:

| Condition | Level |
|---|---|
| No live measurement available | **UNKNOWN** (reported honestly, never faked) |
| Peak value below half the threshold | **NONE** |
| Peak value at half the threshold | **WATCH** |
| Peak value at or above the threshold | **ALERT** |
| Peak value at or above 1.5x the threshold | **SEVERE** |

It also reports which variables were exceeded and which one was the driver, so the
UI can say "the 3-day total is what pushed this over", not just "high risk".

### 7.3 How the two are combined

Function `combine(susceptibility_class, trigger_index)`:

```
alert = the higher of (susceptibility, trigger)
if susceptibility >= HIGH and trigger >= ALERT:
    alert = CRITICAL          # escalation, because both agree
```

The function returns the alert level, both components by name, and a flag
`escalated_because_both_high` so the UI can explain *why* a cell turned red.

### 7.4 The functions in this file

| Function | What it does |
|---|---|
| `classify_trigger(cond)` | Rainfall/soil reading to NONE/WATCH/ALERT/SEVERE |
| `combine(sus, trigger)` | Merges the two into the final alert level |
| `_soil_moisture_index(value)` | Normalises a raw soil-moisture reading to 0-1 |
| `load_cell_features()` | Loads the cached static 41-feature vector per cell |
| `latest()` | Returns the most recent cycle result without recomputing |
| `_cells_for_weather(artifact)` | Picks cells that need live weather |
| `run_cycle(store)` | **The main loop.** Reads conditions, scores every cell, combines, stores |
| `_persist(payload)` | Writes the cycle to SQLite and PostGIS |

### 7.5 What a cycle actually does, step by step

```
1. fetch live rainfall + soil moisture for each cell   (Open-Meteo, hourly)
2. load the cached 41 static features for each cell    (from stage 03/04)
3. run the trained model on the static features        -> susceptibility
4. classify the live rain/soil reading                 -> trigger
5. combine the two                                     -> alert level
6. write to SQLite + PostGIS                           -> the map reads it
```

Measured in the last run: **10 of 10 cells scored, model status `available`**.
Inference cost was **972 ms for all ten cells** - roughly a tenth of a second each.

### 7.6 The schedulers

Three separate clocks run inside the backend. They are separate because the data
they handle changes at completely different speeds - re-downloading a five-day-old
satellite scene every 15 minutes would be pure waste.

| Job | Interval | Env var to change it |
|---|---|---|
| Live risk cycle | every **900 s (15 min)** | `TERRAPULSE_LIVE_INTERVAL` |
| Satellite pull | first after 45 s, then every **86400 s (24 h)** | `TERRAPULSE_SATELLITE_INTERVAL` |
| Feedback loop check | every **86400 s (24 h)** | `TERRAPULSE_FEEDBACK_INTERVAL` |

All three can be turned off with `TERRAPULSE_LIVE_DISABLE=1` (used by the test suite
so tests never hit the network).

### 7.7 Live conditions - where the weather comes from

File: `live_conditions.py`

Pulls hourly rainfall and soil moisture per cell centroid from **Open-Meteo**, then
sums real measured history into the windows that landslide triggering actually depends
on:

```
rainfall_1h      rainfall_24h     rainfall_3d      rainfall_7d
soil_moisture_0_to_7cm   soil_moisture_7_to_28cm   temperature_2m
```

**A fix worth mentioning to judges if asked about data quality.** The earlier version
held only 24 hours of series and *estimated* the 3-day total as `24h x 2.5` and the
7-day as `24h x 5.0`. Those multipliers were invented - a dry week with one wet day
produced a large fake "7-day total". Open-Meteo serves seven days of hourly history,
so all three windows are now **real sums of measured values**.

`summarise_cell()` and `fetch_live_conditions()` do this work. A failed fetch returns
`available=False` with a reason - it never invents a number.

---

## 8. Alerts and multilingual broadcast

### 8.1 Why this exists

A risk score on a dashboard saves nobody. Somebody has to be told, in a language they
read, with enough instruction to act on.

### 8.2 The files

| File | What it does |
|---|---|
| `alerts/cell_broadcast.py` | Builds the actual message text in each language |
| `alerts/service.py` | Decides the broadcast target area, then dispatches |
| `alerts/schemas.py` | The data shapes for a broadcast request and result |

### 8.3 Languages

Three, written into the message builder:

| Code | Language | Headline |
|---|---|---|
| `en` | English | Landslide Warning |
| `hi` | Hindi | भूस्खलन चेतावनी |
| `ne` | Nepali | पहिरो चेतावनी |

Each message carries three fields: a **headline**, a **description** naming the
location and the affected infrastructure, and an **instruction** telling people what
to do. Not just "danger" - "avoid the area and follow local authority instructions".

### 8.4 How the target area is worked out

`_resolve_target(warning, location)` decides who receives the alert:

- If the warning carries a polygon, broadcast inside that polygon.
- If it carries only a point, build the cell polygon from the monitoring location.
- If a cell covers a road corridor, the affected infrastructure is named in the message.

`_risk_cell_polygon(location)` and `_is_polygonal_geometry(geometry)` support this.

### 8.5 Delivery channels

The design uses a **gateway pattern** - the code that builds a message does not care
how it is delivered.

| Gateway | Status | Notes |
|---|---|---|
| `SimulatedCellBroadcastGateway` | Active for the demo | Writes the dispatch to the database so the UI can show exactly what would be sent |
| `TwilioCellBroadcastGateway` | Implemented | Real SMS, needs account credentials |
| `NtfyCellBroadcastGateway` | Implemented | Push notifications, no account needed |

**Why this matters for the demo:** the simulated gateway is not a fake screen - it
stores the fully-composed message, so judges can inspect the exact SMS content that
would go out. Nothing is mocked up in the UI.

---

## 9. Backend reference - every file, explained

Location: `apps/terrapulse/backend/`

### 9.1 Data and pipeline modules

| File | Purpose in one line |
|---|---|
| `pipeline.py` | The seven-stage orchestrator and the runtime inference path |
| `live_pipeline.py` | The 15-minute cycle: conditions + model -> alert -> map |
| `live_conditions.py` | Fetches live rainfall and soil moisture per cell from Open-Meteo |
| `satellite_ingest.py` | Downloads Sentinel-1 and Sentinel-2 windows for each cell |
| `satellite_watch.py` | Runs the satellite pull on its own daily clock |
| `feedback_loop.py` | The automated retraining cycle, behind a safety gate |
| `spatial_db.py` | PostgreSQL + PostGIS layer for spatial questions |
| `weather_service.py` | 24-hour weather forecast feed for the forecast page |
| `forecast_engine.py` | Turns forecast rainfall into an hour-by-hour risk curve |
| `geo_data.py` | Static geographic data for the map (NH-10 route, cells) |
| `regions.py` | Region definitions - NER (Sikkim) and the Nepal case study |
| `nepal_data.py` | Nepal case-study data from HOT, UNOSAT and ICIMOD |
| `event_replay.py` | Reconstructs the environmental conditions around a past event |
| `ml_engine.py` | **Legacy** development model - see 9.5 |
| `main.py` | The FastAPI app: all API endpoints and all RPC functions |
| `_seed.py` | Seeds baseline rows on first boot |

### 9.2 The risk package

| File | Purpose |
|---|---|
| `risk/trained_predictor.py` | **Loads and serves the shipped LightGBM model** |
| `risk/predictor.py` | The development predictor, used by the Storm Simulator |
| `risk/service.py` | Thin service layer that exposes both predictors |
| `risk/schemas.py` | The request and response shapes for risk predictions |

### 9.3 `risk/trained_predictor.py` - the most important file in the backend

| Function | What it does |
|---|---|
| `model_dir()` | Works out which folder holds the model: env override, then the registry's active version, then the shipped default |
| `_registry_active_dir()` | Reads `models/registry.json` so a promoted version is actually served |
| `load_artifact(directory)` | Loads the model, the feature schema, the thresholds and the importances |
| `required_features(schema)` | Lists the 41 feature names the model needs, in order |
| `_risk_class(score)` | Maps a score to LOW/MODERATE/HIGH/CRITICAL using the measured bands |
| `TrainedMLRiskPredictor.predict(features)` | Scores one location and returns the full prediction object |

**Two design decisions here that are worth defending in the demo:**

**1. It refuses to guess.** If a required feature is missing, it raises an error
instead of filling in an average. A prediction built on substituted medians looks
confident and means nothing. The only exception is the short list in
`imputable_features` - columns that are genuinely blank because the source layer does
not cover that point, which training also had to handle.

**2. It explains its own factors.** `contributing_factors` reports the model's
**global** feature importances for the features that were supplied, alongside their
raw values. The module docstring is explicit that this is *not* a per-prediction
attribution - a true per-row explanation needs SHAP, which this module deliberately
does not claim to do.

> **If a judge asks "is this SHAP":** answer no. It is global feature importance
> shown next to the value. We do not claim per-prediction attribution because we have
> not implemented it. That honesty is itself a good answer.

### 9.4 `spatial_db.py` - why PostGIS is in the stack

Storing a latitude and longitude in an ordinary table would not let us ask any of
these questions:

- which cells lie within 25 km of a reported landslide
- which cells intersect the NH-10 corridor
- which cells fall inside a district polygon

| Function | What it does |
|---|---|
| `dsn()` | Reads the connection string, default port **5433** |
| `connect()` | Opens a PostGIS connection |
| `status()` | Reports availability and PostGIS version (3.6) |
| `ensure_schema()` | Creates the tables and geometry columns |
| `upsert_cells(cells)` | Writes monitoring cells as geometry |
| `write_cycle(payload, model_version)` | Writes one risk cycle |
| `upsert_historical_landslides(landslides)` | Loads recorded events |
| `cells_within_metres_of_landslides(metres, limit)` | The proximity query |
| `latest_risk_per_cell()` | Most recent score per cell |
| `record_pipeline_run(...)` | Logs each pipeline execution |

**Note for the demo:** PostGIS runs on **port 5433**, a separate cluster, so the
machine's own 5432 service is untouched. If PostGIS is down, every entry point
degrades gracefully and reports it - the app does not crash without it.

### 9.5 `ml_engine.py` - the legacy development model

This is the **original prototype** model: a Random Forest trained on 1,500
**synthetic** rows with only 9 weather-style features. It is explicitly labelled in
its own docstring as a simulation dataset.

It is **not** the shipped model. It still exists because two features still call it:
the Storm Simulator and the Nepal case-study demo, both of which need a
forecast-style payload ("what if it rains 100 mm") that the trained susceptibility
model does not accept.

**Say this plainly if asked.** Do not claim the Storm Simulator runs the trained
model. It does not, and section 11.3 explains why.

---

## 10. API reference - every endpoint

Base URL: `http://localhost:5000`

### 10.1 Risk prediction

| Endpoint | Method | What it does |
|---|---|---|
| `/api/risk/model-status` | GET | Which model is loaded, its version and its measured metrics |
| `/api/risk/predict` | POST | Score one location with the **development** predictor |
| `/api/risk/predict-batch` | POST | Score many locations - used by the Storm Simulator |
| `/api/risk/predict-trained` | POST | Score one location with the **shipped LightGBM model** |
| `/api/risk/predict-trained-batch` | POST | Batch version of the above |

### 10.2 Live cycle

| Endpoint | Method | What it does |
|---|---|---|
| `/api/live/conditions` | GET | Current measured rainfall and soil moisture per cell |
| `/api/live/risk` | GET | Latest combined risk result per cell |
| `/api/live/refresh` | POST | Force a cycle now instead of waiting for the timer |
| `/api/live/status` | GET | Scheduler health, cycles completed, cells scored |

### 10.3 Satellite

| Endpoint | Method | What it does |
|---|---|---|
| `/api/satellite/status` | GET | Last pull time, imagery counts, and the explicit note that it is **not** a model input |
| `/api/satellite/refresh` | POST | Force a pull now |

### 10.4 Pipeline and spatial

| Endpoint | Method | What it does |
|---|---|---|
| `/api/pipeline/stages` | GET | Describe the seven stages |
| `/api/pipeline/status` | GET | Last pipeline run summary |
| `/api/pipeline/run` | POST | Trigger a pipeline run |
| `/api/spatial/status` | GET | PostGIS availability and version |
| `/api/spatial/cells-near-landslides` | GET | The proximity query - which cells are near recorded events |
| `/api/spatial/latest-risk` | GET | Latest risk per cell from the spatial database |

### 10.5 Feedback loop and verification

| Endpoint | Method | What it does |
|---|---|---|
| `/api/feedback/status` | GET | Pending events, next retrain due, gate settings |
| `/api/feedback/run` | POST | Run the retraining cycle (gated - it may decline) |
| `/api/verifications` | GET | Field/citizen reports, filterable by status |
| `/api/verifications/stats` | GET | Counts by status |
| `/api/verifications/{id}` | GET | One report in full |
| `/api/verifications/{id}/review` | POST | Curator decision - approve or reject |
| `/api/training-buffer` | GET | Approved reports waiting to enter training |
| `/api/training-datasets/build` | POST | Build a curated dataset from approved reports |

### 10.6 Alerts, map and general

| Endpoint | Method | What it does |
|---|---|---|
| `/api/alerts/cell-broadcast/prepare` | POST | Compose the multilingual broadcast, do not send |
| `/api/alerts/cell-broadcast/simulate` | POST | Dispatch through the simulated gateway and record it |
| `/api/route-safety` | GET | Road connectivity status along the corridor |
| `/api/geo` | GET | All map layers - cells, events, infrastructure, routes |
| `/api/event-replay` | GET | Reconstructed conditions around a historical event |
| `/api/forecast` | GET | The next 24 hours of risk per cell |
| `/rpc` | POST | The bridge the React frontend uses to call backend functions |

### 10.7 The 14 RPC functions the frontend calls

`get_locations`, `get_latest_status`, `get_location_detail`, `get_geo_data`,
`get_active_warnings`, `resolve_warning`, `submit_field_verification`,
`get_pending_verifications`, `approve_for_training`, `run_storm_simulation`,
`save_simulation_record`, `reset_simulation`, `get_model_info`, `init_db`.

---

## 11. Frontend - every screen and feature

Location: `apps/terrapulse/frontend/src/`
Stack: React + TypeScript, Vite, Tailwind CSS, MapLibre GL, Recharts.

### 11.1 The app shell - `App.tsx`

`App.tsx` is the single-page shell. It holds all the shared state and decides what to
draw.

**Two modes, switched from the mode menu in the header:**

| Mode | Who it is for | What it shows |
|---|---|---|
| **Authority** | District administration, SDRF, EOC | The full dashboard with all five views |
| **Citizen** | Public and field officers | A separate, mobile-first portal for filing reports only |

**Five views, from the left navigation:**

| View | Label | What it is for |
|---|---|---|
| `overview` | **Risk Map** | The live map. The default screen |
| `forecast` | **24h Forecast** | Same corridor, next 24 hours, with a time scrubber |
| `simulation` | **Storm Simulator** | Replays a severe monsoon scenario step by step |
| `warnings` | **Early Warnings** | The active alert list, with a count badge |
| `curator` | **Curator** | Review queue for field reports, with a badge for pending items |

**The top strip shows four live numbers:** monitored zones, active warnings, average
risk score, and the model status card. The model card reads its name, version and
metrics from the backend - it is not hardcoded. Right now it shows `LightGBM`,
`landslide_v0.4`, recall 84%, ROC-AUC 0.69.

**Region switching** (`contexts/RegionContext.tsx`): two modes, `sih-demo` (NER,
Sikkim corridor) and `case-study` (the Nepal event). Switching region reloads all map
data and clears the selected cell, so the two datasets can never mix on screen.

### 11.2 `GeospatialViewer.tsx` - the map itself

This is the most complex component. It is one MapLibre GL map with many layers stacked
on it, and it serves both the Risk Map view and the Forecast view.

**Layers it draws:**

| Layer source | What it shows |
|---|---|
| `terrain-source` | 3D terrain elevation (MapTiler raster DEM) |
| `maptiler-v3` | Base map - roads, place names, boundaries |
| `nh10-route` | The NH-10 highway corridor, the study route |
| `route-line-src` | Route safety line |
| `evacuation-routes-src` | Evacuation routes |
| `exposure-roads` | Roads exposed to risk |
| `exposure-settlements` | Villages and settlements exposed to risk |
| `risk-data` | The risk cells, coloured by alert level |
| `risk-centroids` | Cell centre points |
| `event-footprints` | Footprints of recorded historical events |
| `historical-data` | Historical landslide points |
| `broadcast-target` | The area an alert is being broadcast to |
| `verification-reports` | Citizen and field-officer report markers |

**2D and 3D.** Pressing 3D tilts the camera to a 60-degree pitch, adds bearing and
flies the camera to the selected cell. `is3D` controls this.

**Clicking a cell** raises `onCellClick`, which sets the selected cell and opens the
XAI panel on the right.

### 11.3 `XAIPanel.tsx` - the explainability panel

Answers "why did the model say that". It reads `contributing_factors` from the
prediction and shows the top five as labelled bars, each with its raw value and a
colour.

**Say it accurately:** these are the model's **global** feature importances shown next
to the values that were supplied for this cell. It is not a per-prediction
attribution.

### 11.4 `ForecastDashboard.tsx` - the 24-hour view

A time scrubber plus a rainfall chart. Dragging the scrubber recolours the map for
that hour. Data comes from `/api/forecast`, which pulls real hourly rainfall from
Open-Meteo and runs it through `forecast_engine.py`.

### 11.5 `StormSimulator.tsx` - the scenario player

Four predefined steps sent through the backend risk pipeline one at a time:

| Step | Rainfall 24h | Soil moisture | What it represents |
|---|---|---|---|
| T+0 | 25 mm | 0.35 | Normal conditions |
| T+10 | 80 mm | 0.52 | Rain building |
| T+20 | 180 mm | 0.72 | Heavy rain, ground saturating |
| T+30 | 320 mm | 0.88 | Extreme scenario |

Each step calls `POST /api/risk/predict-batch`, and the returned cells replace the
map colours so the audience watches risk climb in real time.

**Be precise about this one.** The simulator uses the **development predictor**, not
the trained LightGBM model. It exists to show how a district office would experience
a build-up. Moving it onto the trained model means assembling the same 41-feature
vector for scenario cells, which is a known next step, not a finished feature.

### 11.6 `WarningsPanel.tsx` - the alert list

Lists active warnings grouped by severity, shows the affected infrastructure, and
lets an officer mark a warning resolved (`resolve_warning`). Resolving writes back to
the database, so the warning count in the header updates.

### 11.7 `CellBroadcastModal.tsx` - the mass alert composer

Opens from a warning. Shows the composed message in all three languages, the target
area, and the delivery channel. `SimulatedCellBroadcastGateway` records the dispatch
so the exact message content is auditable afterwards.

### 11.8 `CuratorDashboard.tsx` - the review queue

**This is the human in the loop.** It lists submitted reports, shows each one on a
map with markers, and lets a curator approve or reject with a written reason.

It also shows the **verification quality** the backend computed for each report:

| Quality | How the backend decides it |
|---|---|
| **Location quality** | `precise` if GPS accuracy <= 50 m, `approximate` if <= 500 m, `invalid` if there are no coordinates |
| **Temporal quality** | `exact` if a valid event timestamp exists, otherwise `unknown` |
| **Evidence quality** | Derived from the combination of the two above plus the photo reference |

The point: a report with 2 km accuracy and no timestamp is not treated as equal to a
report with 10 m accuracy and an exact time. The curator sees the difference.

### 11.9 `CitizenApp.tsx` - the citizen portal

A separate, mobile-first screen. A citizen or field officer picks a hazard type, adds
a description and photo, and submits GPS coordinates. It calls
`submit_field_verification` with `source_type: 'citizen'`.

**What happens to a report, end to end:**

```
citizen submits
   -> stored in field_verifications with status 'pending_review'
   -> appears as a marker on the authority map within 60 seconds
   -> appears in the Curator queue
   -> curator approves or rejects
       approved -> enters the training buffer
                -> can be built into a curated dataset
                -> enters the next gated retrain
       rejected -> recorded with a reason, never trains
```

### 11.10 `EventReplay.tsx` - past-event reconstruction

Rebuilds the environmental conditions around a historical event using the Open-Meteo
historical archive (ERA5 reanalysis).

**Say the caveat if asked:** ERA5 is a reanalysis at roughly 9-11 km resolution, not a
direct rain-gauge reading, and the risk values shown are our model's output, not
recorded observations.

### 11.11 Files that exist but are not used

Being honest about this protects you. These components are in the repository but are
**not mounted anywhere** in the running app:

| File | Status |
|---|---|
| `LiveMonitor.tsx` | Not rendered. Its model card now reads live data rather than hardcoded text, so if it is ever wired up it cannot show a wrong model name |
| `LandslideMap.tsx` | Not rendered - superseded by `GeospatialViewer` |
| `RiskMap.tsx` | Not rendered - superseded by `GeospatialViewer` |
| `ZoneDetail.tsx` | Not rendered |
| `AlertsList.tsx` | Not rendered - superseded by `WarningsPanel` |

If a judge spots one, the answer is: superseded during development, kept in the tree,
not part of the running system. Nothing in them affects any number you are shown.

---

## 12. Human in the loop and the feedback loop

### 12.1 Why a human is in the middle

A model that trains on whatever arrives will eventually train on garbage - a duplicate
report, a mis-tagged photo, a prank. So TerraPulse never adds a field report to
training directly. It goes through a curator first.

### 12.2 The verification files

| File | Responsibility |
|---|---|
| `verification/service.py` | The rules: quality scoring, review decisions, dataset building |
| `verification/repository.py` | The storage: reports, review history, audit events |
| `verification/schemas.py` | Normalising hazard types and event-presence values |

**Key functions in `service.py`:**

| Function | What it does |
|---|---|
| `submit_report(submitted)` | Accepts a new report and scores its quality |
| `get_reports(status)` | Lists reports, optionally filtered |
| `review_report(report_id, decision)` | The curator's approve/reject decision |
| `get_stats()` | Counts by status |
| `get_training_buffer()` | Approved but not yet consumed reports |
| `build_dataset(hazard_type, curator_id)` | Records the dataset manifest and marks reports consumed |

**`repository.py` also does duplication protection:**
`find_candidate_duplicates(report_id, hazard_type, latitude, longitude, observed_at)`
flags a new report that looks like an existing one, and `insert_audit_event` keeps a
permanent record of every decision.

### 12.3 The automated retraining cycle

File: `feedback_loop.py`

```
new events -> curator approval -> curated dataset -> retrain a candidate
  -> validate -> promote ONLY if it did not regress -> new active version
```

**The safety gate.** An automatic retrain that can silently make things worse is
dangerous, so a candidate is trained into its **own version folder** and is only
promoted if it does not lose more than **0.02** on leave-one-state-out **recall** or
**ROC-AUC**, compared with the version currently serving.

**It also refuses to run too eagerly:**

| Setting | Default | Meaning |
|---|---|---|
| `MIN_NEW_EVENTS` | 25 | Need at least 25 new curated events |
| `MAX_INTERVAL_DAYS` | 30 | Otherwise retrain at most once a month |
| Tolerance | 0.02 | Maximum allowed regression on recall or ROC-AUC |

**Current state:** 3 curated events pending, so the loop correctly waits. It has
already produced a curated dataset file (`curated_landslide_v0.4.csv`, containing a
real field-officer report from Singhik), so the path is proven end to end.

**Functions:**

| Function | What it does |
|---|---|
| `load_registry()` / `save_registry(reg)` | Read and write `models/registry.json` |
| `active_version()` | Which version is currently serving |
| `next_version_label()` | Names the next candidate version |
| `pending_curated_events(hazard_type)` | How many approved reports await training |
| `due_for_retrain()` | Applies the 25-event / 30-day rule |
| `build_curated_dataset(version, ...)` | Turns approved reports into training rows |
| `train_candidate(version, dataset, verbose)` | Trains into its own folder. Promotes nothing |
| `evaluate_candidate(candidate)` | Applies the 0.02 regression gate |
| `promote(candidate, evaluation, ...)` | Makes it active, or marks it rejected |
| `run_feedback_cycle(force, verbose)` | The whole sequence, start to finish |

**One-line answer for judges:** "Retraining never happens inside the live path. It is
a separate job that has to beat the current model on unseen states before it is
allowed to replace it."

---

## 13. Open items - read this before the demo

These are real. Knowing them before a judge finds them is the difference between a
strong answer and a bad moment.

### 13.1 The retrain base table does not include the Bhuvan columns

**This is the most important item on this list.**

`feedback_loop.py` builds its curated dataset from
`landslide_dataset_v0.1.csv` (56 columns), not from the enriched
`landslide_dataset_v0.2_bhuvan.csv` (65 columns) that the shipped model was trained on.

**What that means:** if the automated retrain ever fires, the candidate model would
be trained **without the Bhuvan geomorphology and lineament features**. The gate
checks recall and ROC-AUC, so a candidate could pass while quietly dropping the
geology layers the current model has.

**Say this if asked** - it is a one-line fix, not a design flaw:
"The retrain path builds from the base table. It needs repointing at the
enriched table so an automated retrain keeps the geology features. That is a
one-line change and it is on the list before we let the loop run unattended."

### 13.2 The Storm Simulator uses the development predictor

It runs on `DevelopmentRiskPredictor`, the 9-feature development contract, not on the
trained LightGBM model. The trained model needs the full 41-feature vector, which
scenario cells do not currently have.

**Do not claim the simulator is the trained model.** The honest framing is that it
demonstrates the alerting workflow; the live map is what runs the trained model.

### 13.3 Only 10 monitoring cells are live

All in Sikkim, along the NH-10 corridor. The model itself is trained on 17,092 points
across eight NER states and scores 0.84 average recall on a state it has never seen -
so it generalises. The live map is a demonstration corridor, and adding cells is a
data-availability question, not a modelling one.

### 13.4 GSI geology is downloaded but not yet a feature

`07_GEOLOGY/GSI` is on disk. Bhuvan geomorphology and lineaments **are** features; the
GSI lithology layer is not yet. Adding it means a retrain and revalidation.

### 13.5 Flood and debris-flow models do not exist

`02_FLOOD_LABELS` and `03_DEBRIS_FLOW_LABELS` hold downloaded data. No flood or
debris-flow model has been trained. The architecture supports it; the labels are
staged.

### 13.6 The score is a ranking, not a probability

Training used a 1:1 case/control sample, so the model's base rate is 0.5 while the
real-world event rate is far lower. A score of 0.7 means "ranks high", not "70%
chance". This is documented in the model code itself.

### 13.7 The live rainfall analysis is not yet a model input

Rainfall in the model is **climatology** - the long-term pattern. Live rainfall drives
the **trigger** layer, not the susceptibility model. Combining them into one model is
the documented next version, and it needs event-time rainfall for the historical
landslides, which is a data problem we have not finished solving.

### 13.8 Some components in the repository are unused

See section 11.11. `LiveMonitor`, `LandslideMap`, `RiskMap`, `ZoneDetail` and
`AlertsList` are not mounted. They do not affect the demo.

---

## 14. Jury question bank

### 14.1 About the model

**Q: What does the AI actually do?**
"It scores how susceptible a location is to a landslide, from 41 features describing
its terrain, soil, land cover, distance to roads and rivers, and geology. A separate
live layer watches rainfall. The map shows the more urgent of the two."

**Q: How accurate is it?**
"On leave-one-state-out - training on every state except one and testing on the state
we held back - the average ROC-AUC is 0.69 and the average recall is 0.84. That means
it catches about five of every six recorded landslides in a region it has never seen."

**Q: Why not report a single accuracy percentage?**
"Because accuracy is misleading here. Only a small share of hillsides actually fail,
so a model that says 'safe' everywhere would score high accuracy and be useless. We
report recall and ROC-AUC because those measure whether we catch the events that
matter."

**Q: Which is more important, precision or recall?**
"Recall. A missed landslide can kill people; a false alarm costs a wasted
deployment. But it is a dial, not a fixed property - the district administration sets
it. We can show the exact cost of any cut-off they choose."

**Q: What is the threshold, and who chose it?**
"It is measured, not invented. Each band was set by testing what it actually catches -
0.28 catches about 80% of real landslides, 0.69 gives 75% precision. Those are
operational bands, and we say so rather than calling them validated severity
classes."

**Q: Did you compare other models?**
"Yes - logistic regression, Random Forest, XGBoost and LightGBM, on identical data
and identical folds. The tree models are statistically tied. LightGBM with the Bhuvan
geology layers was our best measured combination, and at 2 MB it fits an offline
deployment."

**Q: Why not use deep learning?**
"The data is tabular: one row per location with measured features. Gradient-boosted
trees are the correct tool and they are interpretable. A neural network on 41 tabular
features would add cost and remove explainability for no measured gain."

**Q: Is the model explainable?**
"Yes, and we are careful about the claim. We show global feature importance alongside
the supplied values. We do not claim per-prediction attribution because we have not
implemented SHAP."

**Q: What are the top drivers?**
"From the shipped model: distance to road, elevation, distance to water, distance to
river, then soil texture and slope. That ordering is read from the model, not
asserted."

### 14.2 About the data

**Q: Where did your data come from?**
"Ten public sources. Landslide labels from the Geological Survey of India inventory -
8,546 recorded events. Terrain from Copernicus DEM at 30 m. Rainfall from IMD gridded
data, 1991 to 2025. Soil from SoilGrids. Land cover from ESA WorldCover. Roads and
rivers from OpenStreetMap. Geology from ISRO's Bhuvan. Live weather from Open-Meteo."

**Q: Your negatives are fake, aren't they?**
"They are generated, and we say so. Nobody records where a landslide did not happen,
so negatives have to be constructed. Ours are placed away from recorded events and
checked for low slope. That is the standard approach in this literature, and it is
disclosed in the dataset audit file."

**Q: How much data?**
"17,092 training points - 8,546 real landslides and 8,546 verified non-landslide
locations - across 41 features, over eight North-Eastern states."

**Q: Is any value typed in by hand?**
"No. Every feature is computed from its source file at the coordinate being scored,
and the pipeline rebuilds them automatically when a source is republished."

### 14.3 About real-time and the pipeline

**Q: Is this real-time?**
"The operational path is. Live rainfall and soil moisture arrive hourly, a cycle runs
every 15 minutes, and each cell is rescored and redrawn. What does not change hourly
is the terrain - and that is correct, because terrain does not change hourly."

**Q: Does the model retrain live?**
"No, and it should not. A model that updates itself during an emergency cannot be
validated. Retraining is a separate offline job with a gate: the candidate is promoted
only if it does not regress on unseen states."

**Q: Walk me through the pipeline.**
"Seven stages - ingestion, preprocessing, geo processing, feature engineering, model
inference, risk engine, then serve and visualise. Stages one to four build the feature
vector, stage five loads the trained model, six turns the score into an action level,
and seven writes it to the map and the alerts."

**Q: Satellite imagery is in your stack - is it in the model?**
"No, deliberately. It is an observation layer. The model's feature contract is fixed
and validated; adding a band means a full retrain and revalidation. Also, optical
imagery is useless exactly when landslides happen - in heavy cloud and rain."

### 14.4 About resilience and deployment

**Q: What if the internet is down during a disaster?**
"That is a design requirement, not an afterthought, and it is why the model is 2 MB.
The susceptibility model needs no network - terrain, soil, land cover and geology are
static. It runs from a local artifact, and the offline deployment path is the reason
we did not choose a heavier model. What does need the network is live rainfall, and
when a fetch fails the system reports `available: false` with a reason instead of
inventing a number."

**Q: How does it scale to other states?**
"The model already generalises - 0.84 average recall on a state it has never seen.
Adding a region means extracting the same features for new coordinates, which is
scripted, plus its monitoring cells. The scaling limit is data availability, not the
model."

**Q: Why PostGIS?**
"Because the map asks spatial questions - which cells are within 25 km of a recorded
landslide, which intersect the NH-10 corridor, which fall inside a district. Storing
a latitude and longitude in an ordinary table would not let us answer any of those."

### 14.5 About impact

**Q: How does this save lives?**
"By moving the district from reacting to preparing. The system names the cells with
the highest combined susceptibility and rainfall loading *before* failure, and pushes
a warning in a language people read, naming the roads affected - so a district officer
knows where to pre-position and which route to close."

**Q: Who acts on it?**
"District administrations, SDRF and disaster management authorities get the warning
and the priority list. Citizens get the multilingual broadcast."

**Q: What is the weakest part of the system?**
"The negatives are generated rather than observed, and the live rainfall component is
not yet a model input. Both are known, both are documented, and both are the next
version - not things we are hoping nobody notices."

**Q: What would you build next with more time?**
"Three things, in order. First, event-time rainfall for the historical landslides so
live rainfall can enter the model rather than only the trigger layer. Second, the
seven-state scale-up of monitoring cells. Third, the flood and debris-flow models -
the labels are already downloaded."

---

## 15. Script reference

Location: `scripts/`

### 15.1 Building the datasets

| Script | What it does |
|---|---|
| `build_landslide_dataset.py` | Assembles the base training table |
| `build_negatives.py` | Generates the non-landslide points |
| `assign_state_to_points.py` | Tags each point with its state and district |
| `build_curated_dataset.py` | Turns curator-approved reports into real feature rows |
| `merge_landslide_features.py` | Joins all extracted features into one table |
| `merge_bhuvan_features.py` | Joins the Bhuvan geology columns onto the base table |

### 15.2 Extracting features at points

Each of these samples one source raster or layer at a list of coordinates:

| Script | Source |
|---|---|
| `sample_terrain_at_points.py` | Copernicus DEM - elevation, slope, curvature, ruggedness |
| `extract_rainfall_at_points.py` | IMD - rainfall climatology |
| `extract_soil_at_points.py` | SoilGrids - soil texture and chemistry |
| `extract_landcover_at_points.py` | ESA WorldCover - land-cover shares |
| `extract_distances_at_points.py` | OpenStreetMap - distance to roads, rivers, water |
| `bhuvan_fetch_points.py` | Bhuvan WFS - geomorphology and lineaments at points |
| `extract_cell_features.py` | **All of the above in one pass, for the 10 monitoring cells** |
| `fetch_cell_bhuvan.py` | Bhuvan values for the monitoring cells |

### 15.3 Training and evaluation

| Script | What it does |
|---|---|
| `train_landslide_model.py` | **Trains and validates the model.** Writes a new version folder |
| `check_predictions.py` | Holds one state out and shows what the model actually said. Trains only an in-memory copy, saves nothing |
| `model_operating_points.py` | Produces the threshold trade-off table |
| `show_threshold_dial.py` | Shows recall and precision at different alert levels |
| `predict_landslide.py` | Scores a point from the saved artifact |
| `ablation_rf_size.py` | How small can a Random Forest get before it stops performing |
| `ablation_road_dependence.py` | How much the model depends on the road-distance feature |

**Which scripts retrain the model?** Only `train_landslide_model.py` (and
`ablation_rf_size.py`, which is an experiment). `check_predictions.py` fits a
throwaway copy in memory to test on unseen ground and **never writes a model file**.
That distinction matters if anyone asks whether you have been retraining by accident.

### 15.4 Data download and diagnostics

| Script | What it does |
|---|---|
| `download_worldcover.py` | Downloads the ESA WorldCover tiles |
| `terrapulse_sources.py` | Shared source definitions and paths |
| `start_spatial_db.ps1` | Starts the PostGIS cluster on port 5433 |
| `_probe_*.py`, `_inspect_bhuvan_layers.py` | Exploratory probes, not part of the pipeline |

---

## 16. Appendix - running and verifying the system

### 16.1 Start everything

```bash
# spatial database (optional but used by stage 07)
powershell -File scripts/start_spatial_db.ps1

# backend
cd apps/terrapulse/backend
uvicorn main:app --reload --port 5000

# frontend
cd apps/terrapulse/frontend
npm run dev
```

Frontend: http://localhost:5173/    Backend: http://localhost:5000

### 16.2 Verify the pipeline is healthy

```bash
cd apps/terrapulse/backend
python pipeline.py --json          # all seven stages, machine readable
python pipeline.py --live          # the runtime inference path only
python pipeline.py --feedback      # feedback loop status
```

A healthy run ends with `"ok": true` and stage 07 reporting cells written to PostGIS.

### 16.3 Check the live system without opening the UI

```bash
curl http://localhost:5000/api/live/status
curl http://localhost:5000/api/risk/model-status
curl http://localhost:5000/api/pipeline/status
curl http://localhost:5000/api/feedback/status
```

`/api/live/status` is the one to check before a demo. It reports the scheduler
interval, how many cycles have run, how many cells were scored, and whether the model
is available.

### 16.4 Run the test suite

```bash
cd apps/terrapulse/backend
$env:TERRAPULSE_LIVE_DISABLE="1"
python -m pytest tests -q
```

**101 tests pass.** The environment variable stops the scheduler so tests never hit
the network. The suite covers the risk API, the trained predictor, the pipeline
layers, the live cycle, satellite ingestion, source freshness, the verification
workflow, cell broadcast and the geo endpoints.

The test `tests/test_pipeline_layers.py` asserts the live feature count against the
model's own schema, so the feature count can never silently drift out of sync with the
documentation again.

### 16.5 Repository map

```
TERRAPULSE/
  README.md                     project overview
  TERRAPULSE_PRD.md             this document
  model_architecture.md         full technical architecture
  model_evaluation.md           the measured evaluation of the shipped model
  AGENTS.md                     working notes and conventions
  apps/terrapulse/backend/      FastAPI backend, pipeline, model serving
  apps/terrapulse/frontend/     React dashboard and citizen portal
  models/                       trained artifacts and the version registry
  scripts/                      dataset building, extraction, training
  TERRAPULSE_DATA/              the data lake, numbered by pipeline stage
```

### 16.6 The three things to say if you only remember three things

1. **"The model ranks how dangerous a place is. A separate live layer watches the
   rain. The map shows the more urgent of the two."**
2. **"Retraining never happens in the live path. It is a separate job that has to
   beat the current model on unseen states before it can replace it."**
3. **"The threshold is a policy dial, not a model property - we can show the exact
   cost of any cut-off you choose."**

---

## 17. Document control

| | |
|---|---|
| Shipped model | LightGBM, `landslide_v0.4`, 2.1 MB, 41 features |
| Training data | 17,092 points, 8,546 landslide / 8,546 non-landslide |
| Live cells | 10, Sikkim NH-10 corridor |
| Pipeline | 7 stages, `pipeline.py` |
| Live cycle | every 15 minutes, `live_pipeline.py` |
| Satellite pull | every 24 hours, `satellite_watch.py` |
| Feedback loop | 25 events or 30 days, 0.02 regression gate |
| Tests | 101 passing |
| Languages | English, Hindi, Nepali |

All figures in this document were read from the running system and its artifact
files. Where something is not built yet, it is listed in section 13 rather than
implied to work.
"The platform is built multi-hazard — the reporting layer, the curator and the risk contract all take a hazard type, and flood and
 debris-flow labels are already staged in the data lake. The landslide model is the one we have trained and validated end-to-end.
The flood model needs the India Flood Inventory joined to district boundaries, which is the next build, not something we'd rush."