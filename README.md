# TerraPulse.ai

?? **Live Demo:** [https://terrapulse-86te.onrender.com/](https://terrapulse-86te.onrender.com/)
**AI-Based Early Warning and Landslide Risk Monitoring System in the North Eastern Region (NER)**

*SIH 2026 Problem Statement: SIH26001*

## Overview
TerraPulse.ai is a next-generation predictive intelligence platform designed for the complex geological terrain of the North Eastern Region (NER) of India, specifically focusing on the critical NH-10 highway corridor in North Sikkim.

By leveraging real-time antecedent rainfall accumulation, soil moisture indices, and high-resolution slope telemetry, our Gradient Boosting machine learning engine accurately predicts landslide susceptibility *before* failure occurs.

## Key Features

1. **Temporal Storm Simulator:** Replays extreme monsoon scenarios (T+0 to T+50) through the live ML pipeline.
2. **Explainable AI (XAI) Panel:** Transparently visualizes top risk drivers (Rainfall Intensity, Slope Angle) for each geographic cell.
3. **Infrastructure Impact Assessment:** Automatically detects risk propagation onto critical infrastructure (NH-10).
4. **Human-in-the-Loop (HITL) Curation:** Integrates SDRF field verification reports before adding them to the ML training dataset, preventing noisy data from degrading the model.

## Tech Stack
* **Frontend:** React, Tailwind CSS, Vite, Lucide-React, Recharts (EOC Control Room Dark Aesthetic)
* **Backend:** FastAPI, Python 3
* **Machine Learning:** Scikit-learn (Gradient Boosting Classifier Ensemble), Pandas, NumPy
* **Database:** SQLite (Migration-ready for PostgreSQL + PostGIS)

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
npm install --legacy-peer-deps
npm run dev
```

---

