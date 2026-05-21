import os
import json
import glob
from typing import Optional, List
from collections import defaultdict
from datetime import datetime
from groq import Groq
from config import DAILY_SUMMARY_DIR, WEEKLY_SUMMARY_DIR, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

api_key = os.getenv("API_KEY")
client = Groq(api_key=api_key) if api_key else None


def get_latest_daily_summary():
    """Utility for nexus.py /recommend endpoint — reads newest daily summary from disk."""
    if not DAILY_SUMMARY_DIR.exists():
        return None, None

    summary_files = glob.glob(str(DAILY_SUMMARY_DIR / "*.json"))
    if not summary_files:
        return None, None

    latest_file = max(summary_files, key=os.path.getctime)
    try:
        with open(latest_file, "r") as f:
            return json.load(f), latest_file
    except Exception as e:
        print(f"[engine] Error reading summary: {e}")
        return None, None

def get_latest_weekly_summary():
    """Utility for nexus.py /recommend endpoint — reads newest weekly summary from disk."""
    if not WEEKLY_SUMMARY_DIR.exists():
        return None, None

    summary_files = glob.glob(str(WEEKLY_SUMMARY_DIR / "*.json"))
    if not summary_files:
        return None, None

    latest_file = max(summary_files, key=os.path.getctime)
    try:
        with open(latest_file, "r") as f:
            return json.load(f), latest_file
    except Exception as e:
        print(f"[engine] Error reading summary: {e}")
        return None, None


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


def aggregate_anomalies(log_data: list) -> dict:
    """Aggregate a list of raw anomaly records into a structured summary dict on the fly."""
    if not log_data:
        return {
            "report_type": "recent_detections",
            "period": {
                "from": None,
                "to": None,
                "generated_at": datetime.now().isoformat(),
            },
            "overview": {
                "total_anomaly_events": 0,
                "affected_apps": 0,
                "affected_services": 0,
                "availability_percentage": 100.0,
                "average_response_time_ms": None,
                "peak_incident_hour": None,
                "most_common_http_error": None,
            },
            "incident_types": {
                "latency": 0,
                "availability": 0,
                "http_error": 0,
                "drift_only": 0,
            },
            "top_unstable_services": []
        }

    total_confirmed = len(log_data)
    affected_apps     = set()
    affected_services = set()
    global_down       = 0
    global_rt_all     = []
    http_errors_global = defaultdict(int)
    hour_counter      = defaultdict(int)

    services = {}

    for record in log_data:
        app_id   = record.get("id_aplikasi")
        svc_id   = str(record.get("id_service", ""))
        name     = record.get("nama") or ""
        url      = record.get("url", "")
        is_down  = record.get("status") == 0
        http_code = int(record.get("http_status_code", 0))
        rt        = int(record.get("response_time_ms", 0))

        if app_id is not None:
            affected_apps.add(app_id)
        if svc_id:
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
        except (ValueError, TypeError, KeyError):
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

    incident_type_counts = defaultdict(int)
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

    from_time = None
    to_time = None
    valid_checked_ats = [r["checked_at"] for r in log_data if "checked_at" in r]
    if valid_checked_ats:
        from_time = min(valid_checked_ats)
        to_time = max(valid_checked_ats)

    return {
        "report_type": "recent_detections",
        "period": {
            "from":         from_time,
            "to":           to_time,
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
    }


def generate_recommendation(summary_data: dict, summary_path: Optional[str] = None):
    """Generate LLM recommendations from a summary dict and optionally patch them back into the file."""
    if not client:
        print("[engine] API_KEY not set — skipping recommendations.")
        return []

    if summary_data.get("overview", {}).get("total_anomaly_events", 0) == 0:
        print("[engine] No anomalies in summary — skipping recommendations.")
        return []

    overview       = summary_data.get("overview", {})
    incident_types = summary_data.get("incident_types", {})
    top_services   = summary_data.get("top_unstable_services", [])

    prompt_context = (
        f"Overview:\n{json.dumps(overview, indent=2)}\n\n"
        f"Incident Types:\n{json.dumps(incident_types, indent=2)}\n\n"
        f"Top Unstable Services:\n{json.dumps(top_services[:5], indent=2)}"
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages = [
            {
                "role": "system",
                "content": (
                    "Kamu adalah AI observability dan monitoring system profesional.\n"
                    "Tugasmu adalah menganalisis anomaly monitoring report dan menghasilkan rekomendasi operasional yang singkat, teknis, jelas, dan actionable.\n\n"
        
                    "Report dapat berupa DAILY atau WEEKLY report atau RECENT MONITORING report.\n"
                    "Jika WEEKLY report, fokus pada:\n"
                    "- recurring anomalies\n"
                    "- service paling tidak stabil\n"
                    "- availability rendah\n"
                    "- repeated http errors\n"
                    "- latency berkepanjangan\n"
                    "- pola anomaly yang berulang\n\n"
        
                    "Jika DAILY report atau RECENT MONITORING report, fokus pada:\n"
                    "- anomaly paling signifikan\n"
                    "- lonjakan response time\n"
                    "- service down\n"
                    "- http error dominan\n\n"
        
                    "Prioritaskan issue dengan impact terbesar.\n"
                    "Jangan mengulang rekomendasi yang sama.\n"
                    "Gunakan insight langsung dari data yang diberikan.\n\n"
        
                    "Kamu HARUS mengembalikan output JSON valid tanpa markdown.\n\n"
        
                    "Aturan klasifikasi priority:\n"
                    "- critical: service down, banyak 5xx, atau availability turun drastis\n"
                    "- high: latency sangat tinggi atau anomaly berulang terus-menerus\n"
                    "- medium: spike response time atau http error terbatas\n"
                    "- low: anomaly kecil tanpa impact besar\n\n"
        
                    "Format output:\n"
                    "{\n"
                    '  "recommendations": [\n'
                    "    {\n"
                    '      "priority": "critical | high | medium | low",\n'
                    '      "what_happened": "deskripsi singkat masalah utama",\n'
                    '      "recommendation": "langkah remediasi teknis yang actionable"\n'
                    "    }\n"
                    "  ]\n"
                    "}\n\n"
        
                    "Buat 2-5 rekomendasi berdasarkan anomaly paling signifikan."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Berikut monitoring report:\n\n"
                    f"{prompt_context}\n\n"
                    "Analisis report tersebut dan hasilkan rekomendasi operasional."
                )
            }
        ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        recommendations = parsed.get("recommendations", [])

        summary_data["recommendations"] = recommendations
        if summary_path:
            with open(summary_path, "w") as f:
                json.dump(summary_data, f, indent=2)

        return recommendations

    except Exception as e:
        print(f"[engine] LLM generation failed: {e}")
        return []
