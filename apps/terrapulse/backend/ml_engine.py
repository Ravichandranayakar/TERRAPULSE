"""
TerraPulse.ai — ML Risk Engine
Landslide Risk Prediction using Random Forest + XGBoost Benchmarking

IMPORTANT: This module uses a synthetic NER-style dataset for the MVP demo.
The dataset is clearly labelled as simulation/sample data.
The architecture is designed to accept real historical landslide records
from GSI/ISRO when available for production use.

Feature Matrix:
- rainfall_24h_mm: 24-hour rainfall (mm)
- rainfall_3d_mm: 3-day accumulated rainfall (mm)
- rainfall_7d_mm: 7-day antecedent rainfall (mm)
- rainfall_intensity: Hourly rainfall intensity (mm/hr)
- slope_angle: Terrain slope angle (degrees)
- elevation_m: Elevation above sea level (m)
- soil_moisture_index: 0.0 (dry) to 1.0 (saturated)
- base_susceptibility: Static geological susceptibility (0.0 to 1.0)
- historical_count: Number of historical landslide events in cell
"""

import os
import json
import random
import pickle
import numpy as np

# Feature columns used by the model
FEATURE_COLUMNS = [
    "rainfall_24h_mm",
    "rainfall_3d_mm",
    "rainfall_7d_mm",
    "rainfall_intensity",
    "slope_angle",
    "elevation_m",
    "soil_moisture_index",
    "base_susceptibility",
    "historical_count",
]

MODEL_PATH = os.path.join(os.path.dirname(__file__), "data", "terrapulse_model.pkl")


def _generate_training_data():
    """
    Generate NER-appropriate synthetic training dataset.
    Labels are derived from domain-appropriate rules that reflect
    the scientific understanding of Himalayan landslide triggers.
    
    This is clearly a SIMULATION dataset for the MVP demonstration.
    In production, replace with validated GSI/ISRO historical event records.
    """
    random.seed(42)
    np.random.seed(42)
    records = []

    # Generate 1500 synthetic geographic-cell observation records
    for _ in range(1500):
        slope = random.uniform(5, 65)
        elev = random.uniform(400, 4000)
        base_susc = random.uniform(0.1, 0.95)
        hist_count = random.randint(0, 18)

        # Seasonal monsoon patterns (simulate July-Aug peak)
        is_monsoon = random.random() > 0.45
        if is_monsoon:
            intensity = random.uniform(2, 95)
            r24h = random.uniform(20, 200)
            r3d = random.uniform(50, 380)
            r7d = random.uniform(80, 550)
        else:
            intensity = random.uniform(0, 12)
            r24h = random.uniform(0, 40)
            r3d = random.uniform(0, 80)
            r7d = random.uniform(10, 150)

        soil_moisture = min(1.0, (r7d / 500) * 0.6 + (r3d / 300) * 0.3 + random.uniform(0, 0.1))

        # Domain-appropriate labelling logic
        # Reflects Himalayan landslide science: slope + antecedent rainfall are dominant
        risk_score = (
            (slope / 65) * 0.30 +
            (r3d / 380) * 0.25 +
            (r7d / 550) * 0.20 +
            (intensity / 95) * 0.10 +
            base_susc * 0.10 +
            soil_moisture * 0.05
        )

        # Add realistic noise
        risk_score = min(1.0, max(0.0, risk_score + random.gauss(0, 0.03)))

        if risk_score >= 0.75:
            label = 3  # Critical
        elif risk_score >= 0.55:
            label = 2  # High
        elif risk_score >= 0.35:
            label = 1  # Moderate
        else:
            label = 0  # Low

        records.append({
            "rainfall_24h_mm": round(r24h, 1),
            "rainfall_3d_mm": round(r3d, 1),
            "rainfall_7d_mm": round(r7d, 1),
            "rainfall_intensity": round(intensity, 1),
            "slope_angle": round(slope, 1),
            "elevation_m": round(elev, 0),
            "soil_moisture_index": round(soil_moisture, 3),
            "base_susceptibility": round(base_susc, 3),
            "historical_count": hist_count,
            "label": label,
        })

    return records


def train_and_save_model():
    """Train Random Forest model and save to disk."""
    print("[ML_ENGINE] Generating synthetic NER training dataset...")
    records = _generate_training_data()

    X = np.array([[r[c] for c in FEATURE_COLUMNS] for r in records])
    y = np.array([r["label"] for r in records])

    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        # Candidate 1: Random Forest
        rf = RandomForestClassifier(n_estimators=120, max_depth=10, min_samples_leaf=3, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)
        rf_acc = rf.score(X_test, y_test)
        print(f"[ML_ENGINE] Random Forest accuracy on hold-out set: {rf_acc:.3f}")

        # Candidate 2: Gradient Boosting
        gb = GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
        gb.fit(X_train, y_train)
        gb_acc = gb.score(X_test, y_test)
        print(f"[ML_ENGINE] Gradient Boosting accuracy on hold-out set: {gb_acc:.3f}")

        # Select better model
        selected_model = rf if rf_acc >= gb_acc else gb
        selected_name = "Random Forest" if rf_acc >= gb_acc else "Gradient Boosting"
        print(f"[ML_ENGINE] Selected: {selected_name} (acc={max(rf_acc, gb_acc):.3f})")

        # Feature importances
        importances = dict(zip(FEATURE_COLUMNS, selected_model.feature_importances_))
        sorted_importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

        model_bundle = {
            "model": selected_model,
            "model_name": selected_name,
            "accuracy": max(rf_acc, gb_acc),
            "feature_columns": FEATURE_COLUMNS,
            "feature_importances": sorted_importances,
            "rf_accuracy": rf_acc,
            "gb_accuracy": gb_acc,
            "note": "Trained on synthetic NER-style dataset for MVP demonstration. For production, retrain with validated GSI/ISRO historical records.",
        }

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model_bundle, f)

        print(f"[ML_ENGINE] Model bundle saved to {MODEL_PATH}")
        return model_bundle

    except ImportError as e:
        print(f"[ML_ENGINE] sklearn not available: {e}. Using rule-based fallback.")
        return None


def load_model():
    """Load the trained model bundle from disk."""
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    return None


def predict_risk(features: dict, model_bundle=None):
    """
    Predict landslide risk for a single geographic cell.
    
    Args:
        features: dict with keys matching FEATURE_COLUMNS
        model_bundle: loaded model bundle (optional, uses rule-based if None)
    
    Returns:
        dict: {risk_score, risk_level, probability, contributing_factors}
    """
    feat_vector = [features.get(c, 0.0) for c in FEATURE_COLUMNS]

    if model_bundle and model_bundle.get("model"):
        model = model_bundle["model"]
        try:
            X = [feat_vector]
            proba = model.predict_proba(X)[0]
            # probability of class 2 (High) + class 3 (Critical) = risk probability
            risk_prob = float(proba[2] + proba[3])
            predicted_class = int(model.predict(X)[0])
        except Exception:
            risk_prob, predicted_class = _rule_based_predict(features)
    else:
        risk_prob, predicted_class = _rule_based_predict(features)

    # Normalize to 0-100 risk score
    risk_score = round(risk_prob * 100, 1)

    level_map = {0: "low", 1: "moderate", 2: "high", 3: "critical"}
    risk_level = level_map.get(predicted_class, "low")

    # Build contributing factors explanation (XAI)
    contributing_factors = _explain_risk(features, model_bundle)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "probability": round(risk_prob, 3),
        "contributing_factors": contributing_factors,
    }


def _rule_based_predict(features: dict):
    """Fallback rule-based risk prediction when ML model is unavailable."""
    slope = features.get("slope_angle", 0)
    r3d = features.get("rainfall_3d_mm", 0)
    r7d = features.get("rainfall_7d_mm", 0)
    intensity = features.get("rainfall_intensity", 0)
    soil_moisture = features.get("soil_moisture_index", 0)
    base_susc = features.get("base_susceptibility", 0.5)

    score = (
        (slope / 65) * 0.30 +
        (r3d / 380) * 0.25 +
        (r7d / 550) * 0.20 +
        (intensity / 95) * 0.10 +
        base_susc * 0.10 +
        soil_moisture * 0.05
    )
    score = min(1.0, max(0.0, score))

    if score >= 0.75:
        cls = 3
    elif score >= 0.55:
        cls = 2
    elif score >= 0.35:
        cls = 1
    else:
        cls = 0
    return score, cls


def _explain_risk(features: dict, model_bundle=None) -> list:
    """Generate XAI explanation — top contributing risk factors."""
    factors = []

    # Compute normalized contributions
    r3d = features.get("rainfall_3d_mm", 0)
    r7d = features.get("rainfall_7d_mm", 0)
    r24h = features.get("rainfall_24h_mm", 0)
    intensity = features.get("rainfall_intensity", 0)
    slope = features.get("slope_angle", 0)
    soil_moisture = features.get("soil_moisture_index", 0)
    base_susc = features.get("base_susceptibility", 0)
    hist = features.get("historical_count", 0)

    contributions = [
        {"factor": "3-Day Accumulated Rainfall", "value": round(r3d / 3.8, 1), "unit": "%", "raw": r3d, "raw_unit": "mm", "weight": r3d / 380},
        {"factor": "Antecedent Rainfall (7-Day)", "value": round(r7d / 5.5, 1), "unit": "%", "raw": r7d, "raw_unit": "mm", "weight": r7d / 550},
        {"factor": "Slope Angle", "value": round(slope / 0.65, 1), "unit": "%", "raw": slope, "raw_unit": "°", "weight": slope / 65},
        {"factor": "Soil Moisture", "value": round(soil_moisture * 100, 1), "unit": "%", "raw": round(soil_moisture, 2), "raw_unit": "index", "weight": soil_moisture},
        {"factor": "Recent Rainfall (24h)", "value": round(r24h / 2.0, 1), "unit": "%", "raw": r24h, "raw_unit": "mm", "weight": r24h / 200},
        {"factor": "Rainfall Intensity", "value": round(intensity / 0.95, 1), "unit": "%", "raw": intensity, "raw_unit": "mm/hr", "weight": intensity / 95},
        {"factor": "Geological Susceptibility", "value": round(base_susc * 100, 1), "unit": "%", "raw": base_susc, "raw_unit": "index", "weight": base_susc},
        {"factor": "Historical Landslide Activity", "value": round(min(hist / 15, 1) * 100, 1), "unit": "%", "raw": hist, "raw_unit": "events", "weight": hist / 15},
    ]

    # Sort by weight, return top 5
    contributions.sort(key=lambda x: x["weight"], reverse=True)
    return contributions[:5]
