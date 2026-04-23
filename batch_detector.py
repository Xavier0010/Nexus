# - Libraries -
import time
import pymysql
import argparse
import pandas as pd

from detector import AnomalyDetector
from config import (
    TRAINING_CSV,
    DB_ENABLED,
    DB_CONFIG,
    FETCH_QUERY,
    FETCH_INTERVAL_SECONDS,
)


# - Detects anomalies from CSV (dev) -
def detect_csv(detector: AnomalyDetector):
    df = pd.read_csv(str(TRAINING_CSV))
    df["checked_at"] = pd.to_datetime(df["checked_at"])
    df["batch_group"] = df["checked_at"].dt.floor("min")

    total_anomalies = 0

    for batch_time, batch_df in df.groupby("batch_group"):
        batch_df = batch_df.copy()
        batch_df.loc[
            (batch_df["status"] == "DOWN") & (batch_df["response_time_ms"].isnull()),
            "response_time_ms",
        ] = -1
        batch_df = batch_df.drop(columns=["batch_group"])

        print(f"\nBatch: {batch_time} ({len(batch_df)} rows)")

        start = time.perf_counter()
        result = detector.detect(batch_df)
        elapsed = time.perf_counter() - start

        total_anomalies += result["anomalies_found"]

        print(f"  Total: {result['total']} | Anomalies: {result['anomalies_found']} | Time: {elapsed:.3f}s")

        for r in result["results"]:
            if r["is_anomaly"]:
                print(f"  [!] {r['id_aplikasi']} ({r['url']}) -> score: {r['anomaly_score']}")

    print(f"\n{'='*50}")
    print(f"Done. Total anomalies detected: {total_anomalies}")


# - Detects anomalies from DB (prod) -
def detect_database(detector: AnomalyDetector):
    if not DB_ENABLED:
        print("[detector] DB_ENABLED is False in config.py. Cannot fetch from DB.")
        print("[detector] Use CSV mode instead: python batch_detector.py")
        return

    last_id = 0
    print(f"[detector] Starting SQL fetch loop (every {FETCH_INTERVAL_SECONDS}s)")

    while True:
        try:
            connection = pymysql.connect(**DB_CONFIG)
            query = FETCH_QUERY.format(last_id=last_id)
            df = pd.read_sql(query, connection)
            connection.close()

            if df.empty:
                print(f"[detector] No new records (last_id={last_id}).")
            else:
                print(f"[detector] Found {len(df)} new records (id > {last_id})")
                
                result = detector.detect(df)
                last_id = max(int(df["id_log_monitor"].max()), last_id)

                print(f"[detector] Total: {result['total']} | Anomalies: {result['anomalies_found']}")

                for r in result["results"]:
                    if r["is_anomaly"]:
                        print(f"  [!] {r['id_aplikasi']} ({r['url']}) -> score: {r['anomaly_score']}")

        except Exception as e:
            print(f"[detector] Error: {e}")

        time.sleep(FETCH_INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch anomaly detector")
    parser.add_argument("--poll", action="store_true", help="Enable SQL polling mode")
    args = parser.parse_args()

    detector = AnomalyDetector()

    if args.poll:
        detect_database(detector)
    else:
        detect_csv(detector)
