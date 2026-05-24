import os
import sys
import json
import random
from datetime import datetime
from anomaly_detector.detector import AnomalyDetector
from config import ANOMALY_LOG_PATH, FAILED_PAYLOAD_PATH, LOG_DIR


# - Menu -
def print_menu():
    print("\n  NEXUS — Anomaly Detector CLI")
    print("  " + "─" * 32)
    print("  Detector")
    print("    1. Batch Detect (from CSV)")
    print("    2. Batch Detect (from DB)")
    print("    3. Single Detect (manual input)")
    print()
    print("  Model Utilities")
    print("    4. Reload Model")
    print("    5. Retrain Model")
    print()
    print("  Reports")
    print("    6. Generate today's summary")
    print("    7. Generate week's summary")
    print()
    print("  Misc")
    print("    8. Clear anomaly logs")
    print("    9. Clear failed payloads")
    print("    10. Clear summaries")
    print("    0. Exit")
    print("  " + "─" * 32)


# - Actions -
def single_detect():
    print("\n[Single Detect] Leave blank to use defaults.")

    try:
        id_app = input("App ID [1]: ")
        id_app = int(id_app) if id_app.strip() else 1

        url = input("URL [https://api.example.com]: ").strip()
        if not url:
            url = "https://api.example.com"

        status = input("Status (UP/DOWN) [UP]: ").strip().upper()
        if not status:
            status = "UP"

        status_code = input("HTTP Status Code [200]: ")
        status_code = int(status_code) if status_code.strip() else 200

        resp_time = input("  Response Time in ms [150]: ")
        resp_time = int(resp_time) if resp_time.strip() else 150

        now = datetime.now().isoformat()
        record = {
            "id_log_monitor": random.randint(10000, 99999),
            "id_aplikasi": id_app,
            "id_service": "0",
            "url": url,
            "status": status,
            "http_status_code": status_code,
            "response_time_ms": resp_time,
            "checked_at": now,
            "created_at": now,
            "updated_at": now,
        }

        det = AnomalyDetector()
        result = det.detect_single(record)

        print("\n  " + "─" * 28)
        print(f"  Is Anomaly    : {'YES' if result['is_anomaly'] else 'NO'}")
        print(f"  Raw Anomaly   : {'YES' if result['raw_anomaly'] else 'NO'}")
        print(f"  Anomaly Score : {result['anomaly_score']}")
        print(f"  Threshold     : {result['threshold']}")
        print(f"  Strike Count  : {result['strike_count']}")
        print(f"  Recover Count : {result['recovery_count']}")
        print("  " + "─" * 28)

    except Exception as e:
        print(f"\n  [!] Error: {e}")

    input("\nPress Enter to return to menu...")


def reload_model():
    print("\n[Reload Model] Reloading from disk...")
    try:
        det = AnomalyDetector()
        det.reload()
        print(f"Done. Threshold: {round(float(det.threshold), 5)}")
    except Exception as e:
        print(f"  [!] Error: {e}")
    input("\nPress Enter to return to menu...")


def clear_log(label, path, is_json=True):
    print(f"\n[Clear] {label}...")
    try:
        with open(str(path), "w") as f:
            if is_json:
                json.dump([], f)
            else:
                f.write("")
        print(f"Done. {label} cleared.")
    except Exception as e:
        print(f"[!] Error: {e}")
    input("\nPress Enter to return to menu...")


def clear_summaries():
    print("\n[Clear] Summaries...")
    try:
        summary_dir = LOG_DIR / "summary"
        if summary_dir.exists():
            count = 0
            for root, _, files in os.walk(summary_dir):
                for file in files:
                    if (file.startswith("daily_") or file.startswith("weekly_")) and file.endswith(".json"):
                        os.remove(os.path.join(root, file))
                        count += 1
            print(f"Done. {count} summaries cleared.")
        else:
            print("No summaries found.")
    except Exception as e:
        print(f"[!] Error: {e}")
    input("\nPress Enter to return to menu...")


# - Main -
def main():

    while True:
        print_menu()
        choice = input("Select (0-10): ").strip()

        if choice == "1":
            print("\n[Batch Detect] Running from CSV...")
            os.system(f"{sys.executable} -m anomaly_detector.batch_detector")

        elif choice == "2":
            print("\n[Batch Detect] Polling from DB (Ctrl+C to stop)...")
            os.system(f"{sys.executable} -m anomaly_detector.batch_detector --poll")

        elif choice == "3":
            single_detect()

        elif choice == "4":
            reload_model()

        elif choice == "5":
            print("\n[Retrain] Running one-time retrain...")
            os.system(f"{sys.executable} -m anomaly_detector.retrain_scheduler")

        elif choice == "6":
            print("\n[Report] Generating daily summary...")
            os.system(f"{sys.executable} -m report.daily_summary")

        elif choice == "7":
            print("\n[Report] Generating weekly summary...")
            os.system(f"{sys.executable} -m report.weekly_summary")

        elif choice == "8":
            clear_log("Anomaly logs", ANOMALY_LOG_PATH, is_json=True)

        elif choice == "9":
            clear_log("Failed payloads", FAILED_PAYLOAD_PATH, is_json=False)

        elif choice == "10":
            clear_summaries()

        elif choice == "0":
            print("\nGoodbye!\n")
            sys.exit(0)

        else:
            print("\n[!] Invalid option. Enter 0-10.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!\n")
        sys.exit(0)
