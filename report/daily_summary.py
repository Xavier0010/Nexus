import json
import argparse
from collections import defaultdict
from datetime import datetime
from config import (
    ANOMALY_LOG_PATH,
    DAILY_SUMMARY_DIR
)
from report.engine import generate_recommendation


def _classify_incident(ep: dict) -> str:
    has_down     = ep["down_count"] > 0
    has_http_err = bool(ep["http_errors"])
    has_drift    = bool(ep["rt_drifts"])
    has_latency  = ep["avg_rt"] is not None and ep["avg_rt"] > 1000

    if has_down:
        return "availability"
    if has_http_err:
        return "http_error"
    if has_latency:
        return "latency"
    if has_drift:
        return "drift_only"
    return "drift_only"


def _avail_pct(down: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round((1 - down / total) * 100, 2)


def daily_summary():

    DAILY_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(ANOMALY_LOG_PATH, "r") as f:
            log_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log_data = []

    if not log_data:
        print("[summary] No anomalies to summarize.")
        return None

    total_confirmed = len(log_data)

    affected_apps     = set()
    affected_services = set()
    global_down       = 0
    global_rt_all     = []
    http_errors_global = defaultdict(int)
    hour_counter      = defaultdict(int)

    total_raw    = 0
    total_suppressed = 0

    services: dict = {}

    for record in log_data:
        app_id   = record["id_aplikasi"]
        svc_id   = str(record.get("id_service", ""))
        name     = record.get("nama") or ""
        url      = record.get("url", "")
        is_down  = record["status"] == 0
        http_code = int(record.get("http_status_code", 0))
        rt        = int(record.get("response_time_ms", 0))

        if record.get("raw_anomaly"):
            total_raw += 1
            if not record.get("is_anomaly"):
                total_suppressed += 1

        affected_apps.add(app_id)
        affected_services.add(svc_id)

        if is_down:
            global_down += 1
        if rt > 0:
            global_rt_all.append(rt)
        if http_code >= 400:
            http_errors_global[http_code] += 1

        try:
            checked_dt = datetime.fromisoformat(str(record["checked_at"]))
            hour_counter[checked_dt.hour] += 1
        except (ValueError, TypeError):
            pass

        key = svc_id
        if key not in services:
            services[key] = {
                "app_id":     app_id,
                "service_id": svc_id,
                "name":       name,
                "url":        url,
                "anomaly_count": 0,
                "down_count":    0,
                "response_times": [],
                "rt_drifts":     [],
                "http_errors":   defaultdict(int),
            }

        svc = services[key]
        svc["anomaly_count"] += 1
        if is_down:
            svc["down_count"] += 1
        if rt > 0:
            svc["response_times"].append(rt)
        drift = record.get("rt_drift", 0.0)
        if drift:
            svc["rt_drifts"].append(float(drift))
        if http_code >= 400:
            svc["http_errors"][http_code] += 1

        if name:
            svc["name"] = name
        svc["url"] = url

    for svc in services.values():
        rts = svc["response_times"]
        svc["avg_rt"] = round(sum(rts) / len(rts)) if rts else None

    incident_type_counts: dict[str, int] = defaultdict(int)
    for svc in services.values():
        inc = _classify_incident(svc)
        incident_type_counts[inc] += 1

    sorted_svcs = sorted(services.values(), key=lambda x: x["anomaly_count"], reverse=True)

    top_unstable = []
    for svc in sorted_svcs[:10]:
        rts    = svc["response_times"]
        drifts = svc["rt_drifts"]
        http_err = {str(k): v for k, v in svc["http_errors"].items()} if svc["http_errors"] else None

        top_unstable.append({
            "app_id":     svc["app_id"],
            "service_id": svc["service_id"],
            "name":       svc["name"],
            "url":        svc["url"],
            "total_anomaly_events":  svc["anomaly_count"],
            "avg_response_time_ms":  svc["avg_rt"],
            "peak_response_time_ms": max(rts) if rts else None,
            "avg_rt_drift_ms":       round(sum(drifts) / len(drifts), 2) if drifts else None,
            "common_http_errors":    http_err,
            "availability_percentage": _avail_pct(svc["down_count"], svc["anomaly_count"]),
        })

    most_common_err = (
        max(http_errors_global, key=http_errors_global.get)
        if http_errors_global else None
    )
    peak_hour = (
        max(hour_counter, key=hour_counter.get) if hour_counter else None
    )
    avg_rt_global = round(sum(global_rt_all) / len(global_rt_all)) if global_rt_all else None

    summary = {
        "report_type": "daily",
        "period": {
            "from":         min(r["checked_at"] for r in log_data),
            "to":           max(r["checked_at"] for r in log_data),
            "generated_at": datetime.now().isoformat(),
        },

        "overview": {
            "total_anomaly_events":   total_confirmed,
            "affected_apps":          len(affected_apps),
            "affected_services":      len(affected_services),
            "availability_percentage": _avail_pct(global_down, total_confirmed),
            "average_response_time_ms": avg_rt_global,
            "peak_incident_hour":     f"{peak_hour:02d}:00" if peak_hour is not None else None,
            "most_common_http_error": most_common_err,
        },

        "incident_types": {
            "latency":      incident_type_counts.get("latency", 0),
            "availability": incident_type_counts.get("availability", 0),
            "http_error":   incident_type_counts.get("http_error", 0),
            "drift_only":   incident_type_counts.get("drift_only", 0),
        },

        "top_unstable_services": top_unstable,

        "model_performance": {
            "total_predictions":   total_raw,
            "confirmed_anomalies": total_confirmed,
            "suppressed_anomalies": total_suppressed,
        },

        "recommendations": [],
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = DAILY_SUMMARY_DIR / f"daily_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[summary] Saved -> {summary_path.name}")

    generate_recommendation(summary, str(summary_path))

    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anomaly log summarizer — run once to generate today's summary.")
    args = parser.parse_args()
    daily_summary()
