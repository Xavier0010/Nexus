# Nexus API Documentation

Base URL: `http://127.0.0.1:8000`

> Interactive docs also available at `http://127.0.0.1:8000/docs` (Swagger UI) and `http://127.0.0.1:8000/redoc`.

---

## GET /

Health check. Returns all available endpoints grouped by category.

**Response (200):**
```json
{
  "message": "Nexus — Asentinel Anomaly Detector",
  "endpoints": {
    "Detector": {
      "POST /detect": "Single record detection",
      "POST /detect/batch": "Batch detection",
      "POST /reload-model": "Reload the anomaly detection model"
    },
    "Report": {
      "GET /recommend": "Generate recommendations after detection",
      "GET /daily-summary": "Get daily summary (need to be integrated with scheduler)",
      "GET /weekly-summary": "Get weekly summary (need to be integrated with scheduler)"
    },
    "Management": {
      "DELETE /clear-logs/anomalies": "Clear anomaly logs",
      "DELETE /clear-logs/failed": "Clear failed payloads",
      "DELETE /clear-logs/summaries": "Clear summaries"
    }
  }
}
```

---

## POST /detect

Detect anomaly on a single monitoring record. Use this from PHP or any external service that pushes records in real-time.

**Request Body:**
```json
{
  "id_log_monitor": 1,
  "id_aplikasi": 20,
  "id_service": "19",
  "url": "https://www.example.com",
  "status": "DOWN",
  "http_status_code": 503,
  "response_time_ms": -1,
  "checked_at": "2026-04-17 02:26:05",
  "created_at": "2026-04-17 02:26:05",
  "updated_at": "2026-04-17 02:26:05"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id_log_monitor` | int | yes | |
| `id_aplikasi` | int | yes | |
| `id_service` | string | no | `null` if monolithic |
| `url` | string | yes | |
| `status` | string | yes | `"UP"` or `"DOWN"` |
| `http_status_code` | int | yes | |
| `response_time_ms` | int | yes | `-1` if DOWN |
| `checked_at` | string | yes | `YYYY-MM-DD HH:MM:SS` |
| `created_at` | string | yes | `YYYY-MM-DD HH:MM:SS` |
| `updated_at` | string | yes | `YYYY-MM-DD HH:MM:SS` |

**Response (200):**
```json
{
  "id_log_monitor": 1,
  "id_aplikasi": 20,
  "id_service": "19",
  "url": "https://www.example.com",
  "status": 0,
  "http_status_code": 503,
  "response_time_ms": -1,
  "threshold": -0.52707,
  "anomaly_score": -0.64358,
  "raw_anomaly": true,
  "is_anomaly": false,
  "strike_count": 1,
  "recovery_count": 0
}
```

- `raw_anomaly`: `true` if the model score is below threshold (raw, single-check result)
- `is_anomaly`: `true` only after the endpoint has been anomalous for **3 consecutive checks** (confirmed)
- `strike_count`: how many consecutive anomaly detections so far
- `recovery_count`: how many consecutive normal detections so far
- `anomaly_score`: lower = more anomalous
- `threshold`: current model threshold

> Failed payloads (on 500 errors) are automatically saved to `logs/failed_payloads.jsonl`.

---

## POST /detect/batch

Detect anomalies on multiple records at once.

**Request Body:**
```json
{
  "records": [
    {
      "id_log_monitor": 1,
      "id_aplikasi": 20,
      "id_service": "19",
      "url": "https://www.example.com",
      "status": "DOWN",
      "http_status_code": 503,
      "response_time_ms": -1,
      "checked_at": "2026-04-17 02:26:05",
      "created_at": "2026-04-17 02:26:05",
      "updated_at": "2026-04-17 02:26:05"
    }
  ]
}
```

**Response (200):**
```json
{
  "total": 1,
  "anomalies_found": 0,
  "threshold": -0.52707,
  "results": [ "..." ]
}
```

---

## POST /reload-model

Reload the Isolation Forest model, scaler, and threshold from disk without restarting the server. Useful after a retrain.

**Response (200):**
```json
{
  "message": "Model reloaded.",
  "threshold": -0.52707
}
```

---

## GET /recommend

Generate a technical remediation recommendation plan based on the most recent entries in the anomaly log. Calls the LLM engine.

**Query Parameters:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `limit` | int | `100` | Number of most recent anomaly records to analyze. Use `0` for all. |

**Response (200):**
```json
{
  "period": {
    "from": "2026-04-17 02:26:05",
    "to": "2026-04-17 04:17:26",
    "generated_at": "2026-04-23T22:55:50.719207"
  },
  "total_anomalies_analyzed": 42,
  "recommendations": [
    {
      "priority": "critical",
      "what_happened": "Service X has been down for 5 consecutive checks",
      "recommendation": "Restart the service and check upstream dependencies"
    }
  ]
}
```

**Response (404):** No entries in the anomaly log yet.

---

## GET /daily-summary

Returns the most recently generated daily anomaly summary JSON file.

**Response (200):** Full daily summary object (same structure as `logs/summary/daily/daily_*.json`).

**Response (404):** No daily summary has been generated yet. Run the daily summary first (via `main.py` scheduler or `run.py` menu option 6).

---

## GET /weekly-summary

Returns the most recently generated weekly anomaly summary JSON file.

**Response (200):** Full weekly summary object (same structure as `logs/summary/weekly/weekly_*.json`).

**Response (404):** No weekly summary has been generated yet. Run the weekly summary first (via `main.py` scheduler or `run.py` menu option 7).

---

## DELETE /clear-logs/anomalies

Clear the anomaly log file (`logs/anomaly_log.json`), resetting it to an empty array.

**Response (200):**
```json
{ "message": "Anomaly log cleared." }
```

---

## DELETE /clear-logs/failed

Clear the failed payloads log (`logs/failed_payloads.jsonl`).

**Response (200):**
```json
{ "message": "Failed payloads cleared." }
```

---

## DELETE /clear-logs/summaries

Delete all generated daily and weekly summary files under `logs/summary/`.

**Response (200):**
```json
{ "message": "Cleared 14 summaries." }
```

---

## Error Handling

All endpoints return a `500` status with a detail message on unexpected errors:
```json
{ "detail": "error message" }
```

Failed payloads for `/detect` and `/detect/batch` are also persisted to `logs/failed_payloads.jsonl` for later debugging.