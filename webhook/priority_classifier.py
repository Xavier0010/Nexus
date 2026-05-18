from config import (
    CRITICAL_RT_MS,
    CRITICAL_SCORE_MULTIPLIER,
    ESCALATE_STRIKES,
)


def classify(entry: dict) -> str:
    """Return 'critical' or 'warning' for a confirmed anomaly. Rules evaluated top-down, first match wins."""
    http_code  = entry.get("http_status_code")
    status_val = entry.get("status")
    rt_ms      = entry.get("response_time_ms", 0) or 0
    score      = abs(entry.get("anomaly_score", 0) or 0)
    threshold  = abs(entry.get("threshold", 1) or 1)
    strikes    = entry.get("strike_count", 0) or 0

    if http_code is None or http_code == 0 or http_code >= 500:  # connection failure / server error
        return "critical"
    if status_val != 1 and http_code != 200:                      # service down
        return "critical"
    if rt_ms > CRITICAL_RT_MS:                                    # extreme latency
        return "critical"
    if score > threshold * CRITICAL_SCORE_MULTIPLIER:             # severe anomaly score
        return "critical"
    if strikes >= ESCALATE_STRIKES:                               # persistent warning escalation
        return "critical"

    return "warning"
