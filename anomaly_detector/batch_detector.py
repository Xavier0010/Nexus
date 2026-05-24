import time
import argparse
import pandas as pd
from sqlalchemy import text
from anomaly_detector.detector import AnomalyDetector
from webhook.notifier import send_critical, queue_warning, flush_warnings
from webhook.priority_classifier import classify
from config import (
    TRAINING_CSV,
    ENGINE,
    DB_MODE,
    FETCH_QUERY,
    FETCH_INTERVAL_SECONDS,
    NOTIFY_BATCH_LIMIT,
    WEBHOOK_WARNING_INTERVAL_SECONDS,
)

try:
    _NOTIFIER_AVAILABLE = True
except ImportError:
    _NOTIFIER_AVAILABLE = False


def route_anomalies(anomalies: list, label: str = "") -> None:
    if not _NOTIFIER_AVAILABLE:
        return

    count = len(anomalies)
    if count > NOTIFY_BATCH_LIMIT:
        print(f"[notifier] Skipped — {count} anomalies exceeds batch limit ({NOTIFY_BATCH_LIMIT}). Likely historical data.")
        return

    critical = [e for e in anomalies if classify(e) == "critical"]
    warnings  = [e for e in anomalies if classify(e) == "warning"]

    if critical:
        sent = send_critical(critical)
        if sent:
            print(f"[notifier] 🔴 CRITICAL alert sent ({len(critical)} entr{'y' if len(critical) == 1 else 'ies'}). {label}")

    for entry in warnings:
        queue_warning(entry)

    if warnings:
        print(f"[notifier] ⚠️  {len(warnings)} warning(s) queued for digest. {label}")


def detect_csv(detector: AnomalyDetector):
    df = pd.read_csv(str(TRAINING_CSV))
    df["checked_at"] = pd.to_datetime(df["checked_at"])
    df["batch_group"] = df["checked_at"].dt.floor("min")

    total_anomalies = 0

    for batch_time, batch_df in df.groupby("batch_group"):
        batch_df = batch_df.copy()
        batch_df.loc[(batch_df["status"] == "DOWN") & (batch_df["response_time_ms"].isnull()), "response_time_ms"] = -1
        batch_df = batch_df.drop(columns=["batch_group"])

        print(f"\nBatch: {batch_time} ({len(batch_df)} rows)")

        start = time.perf_counter()
        result = detector.detect_batch(batch_df)
        elapsed = time.perf_counter() - start

        total_anomalies += result["anomalies_found"]
        print(f"Total: {result['total']} | Anomalies: {result['anomalies_found']} | Time: {elapsed:.3f}s")

        anomaly_entries = []
        for r in result["results"]:
            if r["is_anomaly"]:
                status_str = "UP" if r["status"] == 1 else "DOWN"
                name_str = r.get("nama") or f"ID:{r['id_aplikasi']}"
                service_str = "Monolithic" if r["id_service"] == "monolithic" else str(r["id_service"]).split(".")[0]
                print(f"[ 🚨 ANOMALY ] {name_str} | Service: {service_str} | URL: {r['url']}")
                print(f"[ ℹ️  INFO ] Status: {status_str} | HTTP: {r['http_status_code']} | RT: {r['response_time_ms']}ms | Score: {r['anomaly_score']}\n")
                anomaly_entries.append(r)
        route_anomalies(anomaly_entries, label=f"(batch {batch_time})")

    # Drain any queued warnings after CSV run completes
    if _NOTIFIER_AVAILABLE:
        sent = flush_warnings()
        if sent:
            print("[notifier] ⚠️  Warning digest sent (end of CSV run).")

    print(f"\n{'='*50}")
    print(f"Done. Total anomalies detected: {total_anomalies}")


def detect_database(detector: AnomalyDetector):
    """
    Entry point for the DB detection loop.
    """
    if DB_MODE == "csv":
        print("[detector] ⚠️  No DB available — falling back to CSV mode.")
        detect_csv(detector)
        return

    if DB_MODE == "none" or ENGINE is None:
        print("[detector] ❌ No data source available. Exiting.")
        return

    tier_label = "Hosted MySQL" if DB_MODE == "mysql" else "Local SQLite"
    print(f"[detector] {tier_label} — starting DB poll loop (every {FETCH_INTERVAL_SECONDS}s)")
    print(f"[notifier] Warning digest interval: {WEBHOOK_WARNING_INTERVAL_SECONDS}s")

    last_id = 0
    is_first_fetch = True
    _last_flush = time.time()

    while True:
        try:
            with ENGINE.connect() as conn:
                query = FETCH_QUERY.format(last_id=last_id)
                df = pd.read_sql(text(query), conn)

            if df.empty:
                print(f"[detector] No new records (last_id={last_id}).")
            else:
                print(f"[detector] Found {len(df)} new records (id > {last_id})")

                result = detector.detect_batch(df)
                last_id = max(int(df["id_log_monitor"].max()), last_id)

                print(f"[detector] Total: {result['total']} | Anomalies: {result['anomalies_found']}")

                anomaly_entries = []
                for r in result["results"]:
                    if r["is_anomaly"]:
                        anomaly_entries.append(r)
                        if not is_first_fetch:
                            status_str = "UP" if r["status"] == 1 else "DOWN"
                            name_str = r.get("nama") or f"ID:{r['id_aplikasi']}"
                            service_str = "Monolithic" if r["id_service"] == "monolithic" else str(r["id_service"]).split(".")[0]
                            print(f"[ 🚨 ANOMALY ] {name_str} | Service: {service_str} | URL: {r['url']}")
                            print(f"[ ℹ️  INFO ] Status: {status_str} | HTTP: {r['http_status_code']} | RT: {r['response_time_ms']}ms | Score: {r['anomaly_score']}")

                if is_first_fetch:
                    print(f"[notifier] Skipped first fetch ({result['anomalies_found']} anomalies).")
                else:
                    route_anomalies(anomaly_entries)

                is_first_fetch = False

        except Exception as e:
            print(f"[detector] DB error: {e}")
            print("[detector] 🔄 Retrying in next cycle...")

        # 3-minute warning digest flush
        now = time.time()
        if _NOTIFIER_AVAILABLE and (now - _last_flush) >= WEBHOOK_WARNING_INTERVAL_SECONDS:
            sent = flush_warnings()
            if sent:
                print("[notifier] ⚠️  Warning digest sent.")
            else:
                print(f"[notifier] No warnings queued (next digest in {WEBHOOK_WARNING_INTERVAL_SECONDS}s).")
            _last_flush = now

        time.sleep(FETCH_INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch anomaly detector")
    parser.add_argument("--poll", action="store_true", help="Enable DB polling mode")
    args = parser.parse_args()

    detector = AnomalyDetector()

    if args.poll:
        detect_database(detector)
    else:
        detect_csv(detector)
