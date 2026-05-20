import json
import os
import pandas as pd
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from anomaly_detector.detector import AnomalyDetector
from config import ANOMALY_LOG_PATH, FAILED_PAYLOAD_PATH, LOG_DIR
from report.engine import generate_recommendation, get_latest_summary


def _log_failed_payload(payload_json: str):
    try:
        with open(str(FAILED_PAYLOAD_PATH), "a") as f:
            f.write(payload_json + "\n")
    except Exception:
        pass


detector = AnomalyDetector()
app = FastAPI(
    title="Nexus — Asentinel Anomaly Detector",
    version="1.2.0",
    description="Anomaly detection API for API health monitoring",
)


class HealthCheckRecord(BaseModel):
    id_log_monitor: int
    id_aplikasi: int
    id_service: Optional[str] = None
    url: str
    status: str
    http_status_code: int
    response_time_ms: int
    checked_at: str
    created_at: str
    updated_at: str

class BatchPayload(BaseModel):
    records: List[HealthCheckRecord]


@app.get("/")
def root():
    return {
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
        },
    }


# --- Detector Endpoint ---
@app.post("/detect")
async def detect_single(data: HealthCheckRecord):
    try:
        result = detector.detect_single(data.model_dump())
        return result
    except Exception as e:
        _log_failed_payload(data.model_dump_json())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect/batch")
async def detect_batch(data: BatchPayload):
    try:
        df = pd.DataFrame([r.model_dump() for r in data.records])
        result = detector.detect_batch(df)
        return result
    except Exception as e:
        _log_failed_payload(data.model_dump_json())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reload-model")
async def reload_model():
    try:
        detector.reload()
        return {
            "message": "Model reloaded.",
            "threshold": round(float(detector.threshold), 5),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Report Endpoint ---
@app.get("/recommend")
async def get_recommendation():
    try:
        summary_data, summary_path = get_latest_summary()
        if not summary_data:
            raise HTTPException(status_code=404, detail="No summary found. Run daily summary first.")
        recommendations = generate_recommendation(summary_data, summary_path)
        return {
            "period": summary_data.get("period"),
            "recommendations": recommendations,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/daily-summary')
async def get_daily_summary():
    try:
        summary_data, summary_path = get_latest_daily_summary()
        if not summary_data:
            raise HTTPException(status_code=404, detail="No dailysummary found. Run daily summary first.")
        return summary_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/weekly-summary')
async def get_weekly_summary():
    try:
        summary_data, summary_path = get_latest_weekly_summary()
        if not summary_data:
            raise HTTPException(status_code=404, detail="No weekly summary found. Run weekly summary first.")
        return summary_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Log Management Endpoint ---
@app.delete("/clear-logs/anomalies")
async def clear_anomaly_log():
    try:
        with open(str(ANOMALY_LOG_PATH), "w") as f:
            json.dump([], f)
        return {"message": "Anomaly log cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear-logs/failed")
async def clear_failed_payloads():
    try:
        with open(str(FAILED_PAYLOAD_PATH), "w") as f:
            f.write("")
        return {"message": "Failed payloads cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear-logs/summaries")
async def clear_summaries():
    try:
        summary_dir = LOG_DIR / "summaries"
        if summary_dir.exists():
            count = 0
            for file in os.listdir(summary_dir):
                if file.startswith("summary_") and file.endswith(".json"):
                    os.remove(summary_dir / file)
                    count += 1
            return {"message": f"Cleared {count} summaries."}
        return {"message": "No summaries found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))