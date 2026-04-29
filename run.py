import os
import sys
from datetime import datetime
import random

def single_detect():
    print("\n[+] Starting Interactive Single Detection...")
    print("    (Leave blank to use default values)")
    
    try:
        id_app = input("  Enter Application ID [1]: ")
        id_app = int(id_app) if id_app.strip() else 1
        
        url = input("  Enter URL [https://api.example.com]: ").strip()
        if not url: url = "https://api.example.com"
        
        status = input("  Enter Status (UP/DOWN) [UP]: ").strip().upper()
        if not status: status = "UP"
        
        status_code = input("  Enter HTTP Status Code [200]: ")
        status_code = int(status_code) if status_code.strip() else 200
        
        resp_time = input("  Enter Response Time in ms [150]: ")
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
            "updated_at": now
        }
        
        print("\n[~] Loading Anomaly Detector (this might take a second)...")
        from detector import AnomalyDetector
        det = AnomalyDetector()
        result = det.detect_single(record)
        
        print("\n" + "="*30)
        print("      DETECTION RESULT")
        print("="*30)
        print(f"Is Anomaly   : {'YES' if result['is_anomaly'] else 'NO'}")
        print(f"Raw Anomaly  : {'YES' if result['raw_anomaly'] else 'NO'}")
        print(f"Anomaly Score: {result['anomaly_score']}")
        print(f"Strike Count : {result['strike_count']}")
        print(f"Recover Count: {result['recovery_count']}")
        print("="*30)
        
        input("\nPress Enter to return to menu...")
    except Exception as e:
        print(f"\n[!] Error during single detection: {e}")
        input("\nPress Enter to return to menu...")

def main():
    while True:
        print("\n" + "="*50)
        print("          NEXUS ANOMALY DETECTOR CLI          ")
        print("="*50)
        print("1. Batch Detect (from CSV)")
        print("2. Batch Detect (from Database Polling)")
        print("3. Single Detect (Interactive prompt)")
        print("4. Start API Server (Single & Batch Detect endpoints)")
        print("5. Retrain Model (Once)")
        print("6. Retrain Model (Continuous 12-hour loop)")
        print("0. Exit")
        print("="*50)
        
        choice = input("\nPlease select an option (0-6): ").strip()
        
        if choice == '1':
            print("\n[+] Starting Batch Detection from CSV...")
            os.system(f"{sys.executable} batch_detector.py")
        elif choice == '2':
            print("\n[+] Starting Batch Detection from Database Polling...")
            os.system(f"{sys.executable} batch_detector.py --poll")
        elif choice == '3':
            single_detect()
        elif choice == '4':
            print("\n[+] Starting FastAPI Server...")
            print("    Endpoints available at http://127.0.0.1:8000")
            print("    Press Ctrl+C to stop the server.")
            os.system(f"{sys.executable} -m uvicorn nexus:app --reload --env-file .env")
        elif choice == '5':
            print("\n[+] Retraining Model...")
            os.system(f"{sys.executable} retrain_scheduler.py")
        elif choice == '6':
            print("\n[+] Starting Retrain Scheduler (12-hour loop)...")
            print("    Press Ctrl+C to stop the scheduler.")
            os.system(f"{sys.executable} retrain_scheduler.py --loop")
        elif choice == '0':
            print("\n[+] Exiting Nexus CLI. Goodbye!")
            sys.exit(0)
        else:
            print("\n[!] Invalid selection. Please enter a number between 0 and 6.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[+] Exiting Nexus CLI. Goodbye!")
        sys.exit(0)
