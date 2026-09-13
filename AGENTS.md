# TERRAPULSE Development Instructions

## Project

TERRAPULSE is a real-time environmental monitoring application.

## Coding

- Use Python 3.12.
- Use type hints.
- Keep functions small and focused.
- Do not introduce unnecessary dependencies.
- Preserve the existing architecture unless there is a strong reason to change it.

## Testing

- Run the relevant tests after making changes.
- Do not claim a feature works unless it has been tested.

## Git

- Do not delete existing functionality without explaining why.
- Keep changes focused on the requested task.

## UI

- Keep the existing design system consistent.
- Do not replace working components unnecessarily.


# AGENTS.md - TerraPulse.ai

## Project Overview

TerraPulse.ai is an AI-based early warning and landslide risk monitoring platform originally built for SIH 2026 (Problem Statement SIH26001). It focuses on the NH-10 highway corridor in North Sikkim (NER, India) and includes a Nepal (Rasuwa / Trishuli corridor) case study.

**Core Architectural Innovation:** The project implements a **Risk Intelligence Fusion Architecture** (a Closed-Loop 4-layer model):
1. **Prediction:** ML model calculates baseline risk based on terrain, slope, elevation, and historical data.
2. **Temporal Forecast:** 24h precipitation simulation escalates risk dynamically based on incoming weather.
3. **Ground Truth (Citizen Portal):** Geo-tagged field reports from citizens and officers provide real-time situational awareness.
4. **Verification & Action:** Authority Dashboard curators verify citizen reports to prioritize emergency response and feed clean data back into the ML loop.

**Goal:** Build out the project to a 100% complete, fully-functional prototype to demonstrate this entire closed-loop pipeline for SIH judges.

## Repo Layout

- `apps/terrapulse/backend/main.py` - FastAPI app, RPC endpoint (`POST /rpc`), REST endpoints (`/api/route-safety`, `/api/event-replay`, `/api/forecast`), SQLite schema, and all exported RPC functions.
- `apps/terrapulse/backend/ml_engine.py` - ML risk engine (feature columns, synthetic NER training data, model train/load/predict).
- `apps/terrapulse/backend/forecast_engine.py` - 24h forecast pipeline (temporal rainfall features + ML predictions).
- `apps/terrapulse/backend/weather_service.py` - Weather forecast fetching.
- `apps/terrapulse/backend/regions.py` - Region registry (`ner_india`, `nepal_case`).
- `apps/terrapulse/backend/geo_data.py` - NER grid cells, NH-10 route, historical landslides, infrastructure.
- `apps/terrapulse/backend/nepal_data.py` - Nepal case-study data.
- `apps/terrapulse/backend/event_replay.py` - Historical event replay timeline.
- `apps/terrapulse/backend/risk/` - Risk feature schemas, normalization, development predictor, and predictor service boundary.
- `apps/terrapulse/frontend/src/` - React app source.
  - `App.tsx` - Main entry point. Contains `appMode` state ('authority' | 'citizen') to toggle between the Admin Dashboard and Citizen Portal via a gear icon dropdown.
  - `features/` - Feature panels (map, forecast, warnings, storm simulator, XAI panel, event replay, etc.).
- `features/CitizenApp.tsx` - Mobile-first citizen reporting portal (ground-truth layer).
- `features/StormSimulator.tsx` - Demo scenario inputs and backend-driven batch risk updates.
  - `components/ui/` - Shared UI primitives (shadcn-style).
  - `contexts/RegionContext.tsx` - Region mode state.
  - `api.ts` - RPC client (fetch + sessionStorage cache).

## Commands

### Backend (run from `apps/terrapulse/backend/`)

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 5000
```

### Frontend (run from `apps/terrapulse/frontend/`)

```bash
npm install --legacy-peer-deps
npm run dev
```

Frontend build: `npm run build`

## Key Conventions

- The backend exposes most functionality through a single `POST /rpc` endpoint. Any new backend function must be added to the `__all__` list in `main.py` or the RPC layer will reject it.
- Frontend calls the backend via `rpcCall()` from `src/api.ts`; do not fetch endpoints directly except for the dedicated REST routes (`/api/route-safety`, `/api/event-replay`, `/api/forecast`).
- Region IDs are strings: `ner_india` (default) and `nepal_case`. Handle both in any region-aware backend or frontend change.
- The ML feature contract lives in `ml_engine.py::FEATURE_COLUMNS`. If you change features, update training data, model loading, and prediction paths together.
- ML training data is currently synthetic and clearly labeled as MVP demo data. Do not claim production-grade model accuracy.
- Keep the early-warning severity scale consistent: `LOW / MODERATE / HIGH / CRITICAL`.
- Frontend styling uses Tailwind CSS with an EOC control-room dark aesthetic. Keep UI consistent with the existing design language.

## Data & Deployment

- SQLite database is created at `apps/terrapulse/backend/data/db/terrapulse.db` on first run; schema is auto-initialized by `init_db()`.
- Model artifact: `apps/terrapulse/backend/data/terrapulse_model.pkl`.
- Deployment is configured in `render.yaml` (backend as Docker web service, frontend as static site).
- CORS currently allows `http://localhost:5173` and `http://127.0.0.1:5173` only; update `main.py` when deploying to new origins.

## Agent Working Rules

- Read files before modifying them; understand existing patterns first.
- Make minimal, focused changes; do not refactor unrelated code.
- Do not commit secrets or API keys. Weather API keys belong in environment variables, never in source.
- Do not edit generated artifacts (`dist/`, `node_modules/`, `__pycache__/`).
- After backend changes, verify the server starts; after frontend changes, verify `npm run build` passes.

## Development Risk Predictor

- The current `/api/risk/predict` and `/api/risk/predict-batch` endpoints use a deterministic development/rule-based predictor only.
- Never describe development scores as trained ML output, calibrated probabilities, validated thresholds, or production predictions.
- The predictor contract is isolated under `apps/terrapulse/backend/risk/`; a future validated model must replace the predictor behind that contract without changing the simulator, map, warning UI, or shared risk state.
- Storm Simulator values are explicitly demo scenario inputs. Scenario time must not directly increase risk; risk changes only when feature inputs change and the backend recalculates.
