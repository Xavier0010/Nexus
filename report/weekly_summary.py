import os
import json
import glob
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from config import (
    DAILY_SUMMARY_DIR,
    WEEKLY_SUMMARY_DIR
)
from report.engine import generate_recommendation


def _load_daily_summaries(days: int = 7) -> list[dict]:
    if not DAILY_SUMMARY_DIR.exists():
        return []

    files = sorted(glob.glob(str(DAILY_SUMMARY_DIR / "daily_*.json")))
    recent = files[-days:] if len(files) >= days else files

    summaries = []
    for path in recent:
        try:
            with open(path, "r") as f:
                summaries.append(json.load(f))
        except Exception as e:
            print(f"[weekly] Could not read {os.path.basename(path)}: {e}")

    return summaries


def _avail_pct(down: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round((1 - down / total) * 100, 2)


def _day_name(date_str: str) -> str:
    try:
        return datetime.fromisoformat(date_str).strftime("%A")
    except (ValueError, TypeError):
        return "Unknown"


def weekly_summary(days: int = 7) -> dict | None:

    WEEKLY_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    daily_summaries = _load_daily_summaries(days)

    if not daily_summaries:
        print("[weekly] No daily summaries found. Run daily summary first.")
        return None

    print(f"[weekly] Aggregating {len(daily_summaries)} daily summary/summaries...")

    total_anomaly_events  = 0
    all_affected_apps     = set()
    all_affected_services = set()
    global_down           = 0
    global_rt_all         = []
    http_errors_global    = defaultdict(int)
    hour_counter          = defaultdict(int)
    day_counter           = defaultdict(int)
    date_trend            = {}
    total_raw             = 0
    total_suppressed      = 0
    days_with_anomalies   = 0

    services: dict = {}

    period_from = None
    period_to   = None

    for daily in daily_summaries:
        period   = daily.get("period", {})
        overview = daily.get("overview", {})
        model    = daily.get("model_performance", {})

        # Period boundaries
        d_from = period.get("from", "")
        d_to   = period.get("to", "")
        if d_from:
            if period_from is None or d_from < period_from:
                period_from = d_from
        if d_to:
            if period_to is None or d_to > period_to:
                period_to = d_to

        events = overview.get("total_anomaly_events", 0)
        total_anomaly_events += events
        all_affected_apps.update(range(overview.get("affected_apps", 0)))
        all_affected_services.update(range(overview.get("affected_services", 0)))

        avail = overview.get("availability_percentage", 100.0)
        down_count = round((1 - avail / 100) * events)
        global_down += down_count

        avg_rt = overview.get("average_response_time_ms")
        if avg_rt:
            global_rt_all.append(avg_rt)

        http_err = overview.get("most_common_http_error")
        if http_err:
            http_errors_global[http_err] += 1

        peak_hour_str = overview.get("peak_incident_hour", "")
        if peak_hour_str:
            try:
                hour = int(peak_hour_str.split(":")[0])
                hour_counter[hour] += events
            except (ValueError, IndexError):
                pass

        if events > 0:
            days_with_anomalies += 1

        trend_date = d_from[:10] if d_from else period.get("generated_at", "")[:10]
        confirmed = model.get("confirmed_anomalies", events)
        if trend_date:
            date_trend[trend_date] = date_trend.get(trend_date, 0) + confirmed
            day_counter[_day_name(trend_date)] += confirmed
        total_raw        += model.get("total_predictions", 0)
        total_suppressed += model.get("suppressed_anomalies", 0)

        for svc in daily.get("top_unstable_services", []):
            key = str(svc.get("service_id", ""))
            if key not in services:
                services[key] = {
                    "app_id":          svc.get("app_id"),
                    "service_id":      key,
                    "name":            svc.get("name", ""),
                    "url":             svc.get("url", ""),
                    "anomaly_count":   0,
                    "down_events":     0,
                    "response_times":  [],
                    "rt_drifts":       [],
                    "http_errors":     defaultdict(int),
                    "days_affected":   0,
                }

            s = services[key]
            s["anomaly_count"] += svc.get("total_anomaly_events", 0)
            s["days_affected"] += 1

            avg = svc.get("avg_response_time_ms")
            if avg:
                s["response_times"].append(avg)

            peak = svc.get("peak_response_time_ms")
            if peak:
                s["response_times"].append(peak)

            drift = svc.get("avg_rt_drift_ms")
            if drift:
                s["rt_drifts"].append(float(drift))

            avail_svc = svc.get("availability_percentage", 100.0)
            svc_events = svc.get("total_anomaly_events", 0)
            s["down_events"] += round((1 - avail_svc / 100) * svc_events)

            for code, count in (svc.get("common_http_errors") or {}).items():
                s["http_errors"][code] += count

            if svc.get("name"):
                s["name"] = svc["name"]
            if svc.get("url"):
                s["url"] = svc["url"]

    affected_apps_count     = max((d.get("overview", {}).get("affected_apps", 0) for d in daily_summaries), default=0)
    affected_services_count = max((d.get("overview", {}).get("affected_services", 0) for d in daily_summaries), default=0)

    avg_rt_global = round(sum(global_rt_all) / len(global_rt_all)) if global_rt_all else None
    avail_global  = _avail_pct(global_down, total_anomaly_events)

    most_common_err = max(http_errors_global, key=http_errors_global.get) if http_errors_global else None
    peak_hour       = max(hour_counter, key=hour_counter.get) if hour_counter else None
    peak_day        = max(day_counter, key=day_counter.get) if day_counter else None
    worst_day       = max(date_trend, key=date_trend.get) if date_trend else None

    sorted_svcs = sorted(services.values(), key=lambda x: x["anomaly_count"], reverse=True)
    top_unstable = []
    for svc in sorted_svcs[:10]:
        rts    = svc["response_times"]
        drifts = svc["rt_drifts"]
        http_err = {str(k): v for k, v in svc["http_errors"].items()} if svc["http_errors"] else None

        top_unstable.append({
            "app_id":                svc["app_id"],
            "service_id":            svc["service_id"],
            "name":                  svc["name"],
            "url":                   svc["url"],
            "days_affected":         svc["days_affected"],
            "total_anomaly_events":  svc["anomaly_count"],
            "avg_response_time_ms":  round(sum(rts) / len(rts)) if rts else None,
            "peak_response_time_ms": max(rts) if rts else None,
            "avg_rt_drift_ms":       round(sum(drifts) / len(drifts), 2) if drifts else None,
            "common_http_errors":    http_err,
            "availability_percentage": _avail_pct(svc["down_events"], svc["anomaly_count"]),
        })

    sorted_trend = sorted(date_trend.items())
    daily_trend = []
    for i, (d, c) in enumerate(sorted_trend):
        if i == 0:
            direction = "Stable"
        elif c > sorted_trend[i - 1][1]:
            direction = "Increasing"
        elif c < sorted_trend[i - 1][1]:
            direction = "Decreasing"
        else:
            direction = "Stable"

        daily_trend.append({
            "date":            d,
            "confirmed_anomaly": c,
            "trend":           direction,
        })

    summary = {
        "report_type": "weekly",
        "period": {
            "from":                 period_from or "",
            "to":                   period_to or "",
            "generated_at":         datetime.now().isoformat(),
            "days_covered":         len(daily_summaries),
            "days_with_anomalies":  days_with_anomalies,
        },
        "overview": {
            "total_anomaly_events":       total_anomaly_events,
            "affected_apps":              affected_apps_count,
            "affected_services":          affected_services_count,
            "availability_percentage":    avail_global,
            "average_response_time_ms":   avg_rt_global,
            "worst_day":                  worst_day,
            "peak_incident_day":          peak_day,
            "peak_incident_hour":         f"{peak_hour:02d}:00" if peak_hour is not None else None,
            "most_common_http_error":     most_common_err,
        },
        "daily_anomaly_trend": daily_trend,
        "incident_types": _aggregate_incident_types(daily_summaries),
        "top_unstable_services": top_unstable,
        "model_performance": {
            "total_predictions":    total_raw,
            "confirmed_anomalies":  total_anomaly_events,
            "suppressed_anomalies": total_suppressed,
        },
        "recommendations": [],
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = WEEKLY_SUMMARY_DIR / f"weekly_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[weekly] Saved -> {summary_path.name}")

    generate_recommendation(summary, str(summary_path))

    return summary


def _aggregate_incident_types(daily_summaries: list[dict]) -> dict:
    """Sum incident type counts across all daily summaries."""
    totals = defaultdict(int)
    for daily in daily_summaries:
        for inc_type, count in daily.get("incident_types", {}).items():
            totals[inc_type] += count
    return {
        "latency":      totals.get("latency", 0),
        "availability": totals.get("availability", 0),
        "http_error":   totals.get("http_error", 0),
        "drift_only":   totals.get("drift_only", 0),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly anomaly summary — run once to aggregate the last N daily summaries.")
    parser.add_argument("--days", type=int, default=7, help="Number of past daily summaries to aggregate (default: 7)")
    args = parser.parse_args()
    weekly_summary(days=args.days)

