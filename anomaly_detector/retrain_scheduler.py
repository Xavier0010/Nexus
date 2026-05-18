import time
import argparse
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from anomaly_detector.feature_engineer import build_features
from config import (
    MODEL_PATH,
    SCALER_PATH,
    THRESHOLD_PATH,
    MODEL_PARAMS,
    THRESHOLD_PERCENTILE,
    TRAINING_CSV,
    TRAINING_QUERY,
    DB_ENABLED,
    ENGINE
)


def fetch_training_data() -> pd.DataFrame:
    if DB_ENABLED:
        try:
            with ENGINE.connect() as conn:
                df = pd.read_sql(text(TRAINING_QUERY), conn)
            print(f"[retrain] Fetched {len(df)} rows from database.")
            return df
        except Exception as e:
            print(f"[retrain] DB fetch failed, using CSV: {e}")

    df = pd.read_csv(str(TRAINING_CSV))
    print(f"[retrain] Loaded {len(df)} rows from {TRAINING_CSV.name}")
    return df


def retrain_model(detector=None) -> dict:
    start = time.perf_counter()
    print(f"\n{'='*50}")
    print(f"[retrain] Starting retrain: {datetime.now().isoformat()}")

    df = fetch_training_data()
    _, feature_df = build_features(df)
    print(f"[retrain] Features built: {feature_df.shape}")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(feature_df)

    model = IsolationForest(**MODEL_PARAMS)
    model.fit(X_scaled)

    scores = model.score_samples(X_scaled)
    threshold = float(np.percentile(scores, THRESHOLD_PERCENTILE))

    joblib.dump(model, str(MODEL_PATH))
    joblib.dump(scaler, str(SCALER_PATH))
    joblib.dump(threshold, str(THRESHOLD_PATH))

    elapsed = time.perf_counter() - start

    print(f"[retrain] Model saved to {MODEL_PATH}")
    print(f"[retrain] Threshold: {threshold:.5f}")
    print(f"[retrain] Duration: {elapsed:.2f}s")
    print(f"[retrain] Training rows: {len(df)}")
    print(f"[retrain] Done: {datetime.now().isoformat()}")
    print(f"{'='*50}\n")

    if detector is not None:
        detector.reload()
        print("[retrain] Model reloaded.")

    return {
        "training_rows": len(df),
        "threshold": round(threshold, 5),
        "duration_seconds": round(elapsed, 2),
        "retrained_at": datetime.now().isoformat(),
    }


def retrain_loop():
    print("[retrain] Loop mode: retraining every hour")

    while True:
        try:
            retrain_model()
        except Exception as e:
            print(f"[retrain] Error during retrain: {e}")

        print("[retrain] Next retrain in 1h.\n")
        time.sleep(3600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain anomaly detection model")
    parser.add_argument("--loop", action="store_true", help="Run in loop mode (retrain every 12h)")
    args = parser.parse_args()

    if args.loop:
        retrain_loop()
    else:
        result = retrain_model()
