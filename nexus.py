# Libraries
import os
import json
import joblib
import numpy as np
import pandas as pd
from groq import Groq
from pathlib import Path
from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List
from feature_engineer import build_features

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Welcome to Nexus for Asentinel"}

# Anomaly Detector endpoint
class HealthCheckPayload(BaseModel):
    id_log_monitor: int
    id_aplikasi: int
    id_service: Optional[float] = None
    url: str
    status: str
    http_status_code: int
    response_time_ms: int
    checked_at: str
    created_at: str
    updated_at: str

class BatchPayload(BaseModel):
    records: List[HealthCheckPayload]
    
model = joblib.load("models/model.pkl")
scaler = joblib.load("models/scaler.pkl")
threshold = joblib.load("models/threshold.pkl")

ANOMALY_LOG_PATH = "logs/anomaly_log.json"
FAILED_PAYLOAD_PATH = "logs/failed_payloads.jsonl"
Path("logs").mkdir(exist_ok=True)

@app.post("/predict")
async def predict(data: BatchPayload):
    try:
        df = pd.DataFrame([r.dict() for r in data.records])
        original_df, preproc_df = build_features(df)
        
        scaled = scaler.transform(preproc_df)
        scores = model.score_samples(scaled)
        is_anomalies = scores < threshold

        if os.path.exists(ANOMALY_LOG_PATH):
            with open(ANOMALY_LOG_PATH, "r") as f:
                anomaly_log = json.load(f)
        else:
            anomaly_log = []

        results = []
        for i, (score, is_anomaly) in enumerate(zip(scores, is_anomalies)):
            row = original_df.iloc[i]
            preproc_row = preproc_df.iloc[i]
            is_anomaly = bool(is_anomaly)

            if is_anomaly:
                anomaly_log.append({
                    "id_log_monitor": int(row['id_log_monitor']),
                    "id_aplikasi": int(row['id_aplikasi']),
                    "id_service": str(row['id_service']),
                    "url": str(row['url']),
                    "status": int(row['status']),
                    "http_status_code": int(row['http_status_code']),
                    "response_time_ms": int(row['response_time_ms']),
                    "anomaly_score": round(float(score), 5),
                    "rolling_fail_rate": round(float(preproc_row['rolling_fail_rate']), 5),
                    "rolling_avg_response_time": round(float(preproc_row['rolling_avg_response_time']), 5),
                    "consecutive_failures": int(preproc_row['consecutive_failures']),
                    "checked_at": str(row['checked_at']),
                })

            results.append({
                "id_aplikasi": int(row['id_aplikasi']),
                "id_service": row['id_service'],
                "url": row['url'],
                "is_anomaly": is_anomaly,
                "anomaly_score": round(float(score), 5)
            })

        with open(ANOMALY_LOG_PATH, "w") as f:
            json.dump(anomaly_log, f, indent=2)

        return {
            "total": len(results),
            "anomalies_found": sum(1 for r in results if r['is_anomaly']),
            "threshold": round(float(threshold), 5),
            "result": results
        }

    except Exception as e:
        with open("logs/failed_payloads.jsonl", "a") as f:
            f.write(data.model_dump_json() + "\n")
        return {"error": str(e), "is_anomaly": None}

@app.delete("/clear-anomaly-log")
async def clear_anomaly_log():
    try:
        with open(ANOMALY_LOG_PATH, "w") as f:
            json.dump([], f)
        return {"message": "Anomaly log cleared."}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/clear-failed-payloads")
async def clear_failed_payloads():
    try:
        with open(FAILED_PAYLOAD_PATH, "w") as f:
            json.dump([], f)
        return {"message": "Failed payloads cleared."}
    except Exception as e:
        return {"error": str(e)}

# Recommendation endpoint

# def recommend(data: dict):
#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=[
#             {
#                 "role": "system",
#                 "content": (
#                     "Kamu adalah sistem monitoring API profesional. "
#                     "Tugasmu adalah menganalisis anomali yang terdeteksi dan memberikan rekomendasi teknis yang singkat, jelas, dan actionable. "
#                     "Jawab hanya dengan 3 langkah remediasi dalam format bernomor. "
#                     "Tidak perlu basa-basi atau penjelasan panjang."
#                 )
#             },
#             {
#                 "role": "user",
#                 "content": (
#                     f"Anomali terdeteksi pada API monitoring dengan detail berikut:\n"
#                     f"List API affected: {api_affected}"
#                     f"Berikan 3 langkah remediasi teknis yang harus segera dilakukan."
#                 )
#             }
#         ],

#         temperature=0.3,
#         max_tokens=300
#     )

#     raw = response.choices[0].message.content
#     steps = [step.strip() for step in raw.split('\n') if step.strip()]
#     return steps

# load_dotenv()
# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# @app.post("/recommend")
# async def recommend(data: HealthCheckPayload):
    