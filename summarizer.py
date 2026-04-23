# - Libraries -
import os
import json
from collections import defaultdict
from datetime import datetime

from config import (
    LOG_DIR, 
    ANOMALY_LOG_PATH,
)

SUMMARY_DIR = LOG_DIR / "summaries"

def generate_summary():
    """Reads the anomaly log, generates a summary, and clears the log."""
    
    # Ensure summaries directory exists
    SUMMARY_DIR.mkdir(exist_ok=True)
    
    # Read the log
    try:
        with open(ANOMALY_LOG_PATH, "r") as f:
            log_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log_data = []

    if not log_data:
        print("[summary] No anomalies to summarize.")
        return None

    # Processing variables
    first_seen = min(log_data, key=lambda x: x["checked_at"])["checked_at"]
    last_seen = max(log_data, key=lambda x: x["checked_at"])["checked_at"]
    generated_at = datetime.now().isoformat()
    
    affected_apps = set()
    affected_urls = set()
    down_count_total = 0
    http_errors_counter = defaultdict(int)
    
    apis_stats = {}

    for record in log_data:
        app_id = record["id_aplikasi"]
        url = record["url"]
        key = f"{app_id}_{url}"
        
        affected_apps.add(app_id)
        affected_urls.add(url)
        
        if record["status"] == 0:
            down_count_total += 1
            
        if record["http_status_code"] >= 400:
            http_errors_counter[record["http_status_code"]] += 1
            
        if key not in apis_stats:
            apis_stats[key] = {
                "id_aplikasi": app_id,
                "url": url,
                "id_service": record["id_service"],
                "anomaly_count": 0,
                "scores": [],
                "down_count": 0,
                "http_errors": defaultdict(int),
                "response_times": [],
                "consecutive_failures": []
            }
            
        stats = apis_stats[key]
        stats["anomaly_count"] += 1
        stats["scores"].append(record["anomaly_score"])
        
        if record["status"] == 0:
            stats["down_count"] += 1
            
        if record["http_status_code"] >= 400:
            stats["http_errors"][record["http_status_code"]] += 1
            
        if record["response_time_ms"] > 0:
            stats["response_times"].append(record["response_time_ms"])
            
        stats["consecutive_failures"].append(record["consecutive_failures"])

    # Format the affected APIs list
    formatted_apis = []
    for key, stats in apis_stats.items():
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        worst_score = min(stats["scores"]) if stats["scores"] else 0
        avg_response = sum(stats["response_times"]) / len(stats["response_times"]) if stats["response_times"] else -1
        max_failures = max(stats["consecutive_failures"]) if stats["consecutive_failures"] else 0
        
        formatted_apis.append({
            "id_aplikasi": stats["id_aplikasi"],
            "url": stats["url"],
            "id_service": stats["id_service"],
            "anomaly_count": stats["anomaly_count"],
            "avg_anomaly_score": round(avg_score, 5),
            "worst_score": round(worst_score, 5),
            "down_count": stats["down_count"],
            "http_errors": dict(stats["http_errors"]),
            "avg_response_time_ms": round(avg_response, 2) if avg_response != -1 else -1,
            "max_consecutive_failures": max_failures
        })

    # Sort APIs by anomaly count descending
    formatted_apis.sort(key=lambda x: x["anomaly_count"], reverse=True)

    # Top anomalies API (Top 5)
    top_anomalies_api = [
        f"{api['url']} ({api['anomaly_count']} anomalies)" for api in formatted_apis[:5]
    ]

    # Most common HTTP error
    most_common_error = None
    if http_errors_counter:
        most_common_error = max(http_errors_counter, key=http_errors_counter.get)

    down_percentage = (down_count_total / len(log_data)) * 100 if log_data else 0

    # Build the final summary
    summary = {
        "summary_period": {
            "from": first_seen,
            "to": last_seen,
            "generated_at": generated_at
        },
        "overview": {
            "total_anomalies": len(log_data),
            "total_affected_apps": len(affected_apps),
            "total_affected_urls": len(affected_urls),
            "most_common_http_error": most_common_error,
            "down_percentage": round(down_percentage, 2)
        },
        "top_anomalies_API": top_anomalies_api,
        "affected_apis": formatted_apis
    }

    # Save summary
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_filename = SUMMARY_DIR / f"summary_{timestamp}.json"
    
    with open(summary_filename, "w") as f:
        json.dump(summary, f, indent=2)
        
    print(f"[summary] Generated {summary_filename}")

    # Clear the anomaly log
    with open(ANOMALY_LOG_PATH, "w") as f:
        json.dump([], f)
    print("[summary] Cleared anomaly_log.json")

    return summary

if __name__ == "__main__":
    generate_summary()
