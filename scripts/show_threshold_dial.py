import os
import joblib
import pandas as pd
from sklearn.metrics import recall_score, precision_score, f1_score, confusion_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DATA_FILE = os.path.join(REPO_ROOT, "TERRAPULSE_DATA", "13_MODEL_DATASETS", "landslide_dataset_v0.1.csv")
MODEL_FILE = os.path.join(REPO_ROOT, "models", "landslide_v0.1", "xgb.joblib")

import sys
sys.path.append(HERE)
from train_landslide_model import select_features

def main():
    print(f"Loading dataset: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE)
    
    print(f"Loading model: {MODEL_FILE}")
    model = joblib.load(MODEL_FILE)
    
    # Extract features using the EXACT schema the model was trained on
    X, y, _, _, _, _, _ = select_features(df)
    
    print("Computing probabilities for all points...")
    # Get probability of class 1 (landslide)
    probs = model.predict_proba(X)[:, 1]
    
    print("\n===================================================================")
    print("       THE ALERT DIAL: PRECISION vs RECALL TRADE-OFF               ")
    print("===================================================================")
    print("Threshold | Recall (Caught%) | Precision (Real%) | False Alarms")
    print("-------------------------------------------------------------------")
    
    thresholds = [0.20, 0.30, 0.40, 0.50, 0.53, 0.60, 0.70, 0.80]
    
    total_slides = sum(y == 1)
    
    for t in thresholds:
        preds = (probs >= t).astype(int)
        
        rec = recall_score(y, preds, zero_division=0)
        prec = precision_score(y, preds, zero_division=0)
        f1 = f1_score(y, preds, zero_division=0)
        cm = confusion_matrix(y, preds)
        
        # cm[0][1] is False Positives (False Alarms)
        # cm[1][1] is True Positives (Caught)
        false_alarms = cm[0][1]
        caught = cm[1][1]
        
        marker = " <--- Chosen for v0.1" if t == 0.53 else ""
        
        print(f"   {t:.2f}    |     {rec*100:4.1f}%       |      {prec*100:4.1f}%      |    {false_alarms:<5}   {marker}")
    
    print("===================================================================")
    print("Reading this table:")
    print("- Lowering the threshold catches MORE landslides (higher Recall).")
    print("- But it triggers MORE false alarms (lower Precision).")
    print("- The optimal setting depends on the disaster management authority.")

if __name__ == "__main__":
    main()
