# Nexus API Documentation

Base URL: `http://127.0.0.1:8000`

---

## GET /

Health check. Returns available endpoints.

**Response:**
```json
{
  "message": "Nexus — Asentinel Anomaly Detector",
  "endpoints": {
    "POST /detect": "Single record detection",
    "POST /detect/batch": "Batch detection",
    "GET /recommend": "Generate recommendations from the latest summary"
  }
}
```
---

## POST /detect

Detect anomaly on a single record. Use this from PHP or any external service.

**Request Body:**
```json
{
  "id_log_monitor": 1,
  "id_aplikasi": 20,
  "id_service": 19.0,
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
| `id_service` | float | no | `null` if monolithic |
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
  "threshold": -0.58352,
  "id_log_monitor": 1,
  "id_aplikasi": 20,
  "id_service": "19",
  "url": "https://www.example.com",
  "status": 0,
  "http_status_code": 503,
  "response_time_ms": -1,
  "anomaly_score": -0.64358,
  "raw_anomaly": true,
  "is_anomaly": false,
  "strike_count": 1,
  "recovery_count": 0
}
```

- `raw_anomaly`: `true` if the model score is below threshold (raw, single-check result)
- `is_anomaly`: `true` only after the endpoint has been anomalous for **3 consecutive checks** (confirmed)
- `strike_count`: how many consecutive anomaly detections so far (resets on normal check)
- `recovery_count`: how many consecutive normal detections so far (resets on anomaly check)
- `anomaly_score`: lower = more anomalous
- `threshold`: current model threshold

> **Note:** `is_anomaly` won't be `true` on the first anomalous check. The endpoint must fail 3 times in a row before it's flagged. This prevents false alarms from temporary lag. Configurable via `CONFIRM_STRIKES` and `RECOVER_STRIKES` in `config.py`.

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
      "id_service": 19.0,
      "url": "https://www.example.com",
      "status": "DOWN",
      "http_status_code": 503,
      "response_time_ms": -1,
      "checked_at": "2026-04-17 02:26:05",
      "created_at": "2026-04-17 02:26:05",
      "updated_at": "2026-04-17 02:26:05"
    },
    {
      "id_log_monitor": 2,
      "id_aplikasi": 1,
      "id_service": null,
      "url": "https://www.example.com",
      "status": "UP",
      "http_status_code": 200,
      "response_time_ms": 150,
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
  "total": 2,
  "anomalies_found": 0,
  "threshold": -0.58352,
  "results": [
    {
      "id_log_monitor": 2,
      "id_aplikasi": 1,
      "id_service": "monolithic",
      "url": "https://www.example.com",
      "status": 1,
      "http_status_code": 200,
      "response_time_ms": 150,
      "anomaly_score": -0.41882,
      "raw_anomaly": false,
      "is_anomaly": false,
      "strike_count": 0,
      "recovery_count": 1
    },
    {
      "id_log_monitor": 1,
      "id_aplikasi": 20,
      "id_service": "19",
      "url": "https://www.example.com",
      "status": 0,
      "http_status_code": 503,
      "response_time_ms": -1,
      "anomaly_score": -0.64358,
      "raw_anomaly": true,
      "is_anomaly": false,
      "strike_count": 1,
      "recovery_count": 0
    }
  ]
}
```

Same response fields as `/detect`. The `anomalies_found` count only includes confirmed anomalies (`is_anomaly: true`), not raw detections.

---

## GET /recommend

Generate a technical recommendation plan based on the latest anomaly summary. This endpoint uses the Groq LLM to analyze the summary and provide actionable steps.

**Request Body:** none

**Response (200):**
```json
{
  "period": {
    "from": "2026-04-17 02:26:05",
    "to": "2026-04-17 04:17:26",
    "generated_at": "2026-04-23T22:55:50.719207"
  },
  "recommendation": [
    "1. Lakukan investigasi mendalam terhadap server yang menjalankan API https://www.amd.com dan https://www.netflix.com, karena keduanya memiliki jumlah anomali dan HTTP error yang sangat tinggi.",
    "2. Periksa konfigurasi load balancer dan reverse proxy untuk memastikan tidak ada masalah yang menyebabkan tingginya response time pada beberapa API.",
    "3. Evaluasi kembali kapasitas infrastruktur server untuk mengakomodasi tingginya traffic dan mencegah server crash."
  ]
}
```

---

## POST /reload-model

Reload the model from disk. Call this after retraining to apply the new model without restarting the server.

**Request Body:** none

**Response (200):**
```json
{
  "message": "Model reloaded.",
  "threshold": -0.58352
}
```

---

## DELETE /logs/anomalies

Clear the anomaly log file (`logs/anomaly_log.json`).

**Response (200):**
```json
{
  "message": "Anomaly log cleared."
}
```

---

## DELETE /logs/failed

Clear the failed payloads log (`logs/failed_payloads.jsonl`).

**Response (200):**
```json
{
  "message": "Failed payloads cleared."
}
```

---

## Error Response

All endpoints return this on failure:

**Response (500):**
```json
{
  "detail": "(error message here)"
}
```

Failed payloads for `/detect` and `/detect/batch` are automatically saved to `logs/failed_payloads.jsonl`.