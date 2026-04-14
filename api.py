import pandas as pd
import numpy as np
import joblib
from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()
model = joblib.load("anomaly_detector_model.pkl")
scaler = joblib.load("scaler.pkl")
score_range = joblib.load('score_range.pkl')

class APICheck(BaseModel):
    status: int
    response_time_ms: float
    batch_index: int

def recommend(data: dict):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "Kamu adalah sistem monitoring API profesional. "
                    "Tugasmu adalah menganalisis anomali yang terdeteksi dan memberikan rekomendasi teknis yang singkat, jelas, dan actionable. "
                    "Jawab hanya dengan 3 langkah remediasi dalam format bernomor. "
                    "Tidak perlu basa-basi atau penjelasan panjang."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Anomali terdeteksi pada API monitoring dengan detail berikut:\n"
                    f"- Status API: {'Down' if data['status'] == 0 else 'Up'}\n"
                    f"- Response Time: {data['response_time_ms']} ms\n"
                    f"- Batch Index: {data['batch_index']}\n"
                    f"- Confidence Anomali: {data['confidence']}\n\n"
                    f"Berikan 3 langkah remediasi teknis yang harus segera dilakukan."
                )
            }
        ],

        temperature=0.3,
        max_tokens=300
    )

    raw = response.choices[0].message.content
    steps = [step.strip() for step in raw.split('\n') if step.strip()]
    return steps

@app.get("/")
def root():
    return {"message": "Anomaly Detector + Recommendation API"}

@app.post("/analyze_data")
def analyze(data: APICheck):
    features = pd.DataFrame([[
        data.status,
        data.response_time_ms,
        data.batch_index
    ]], columns=['status', 'response_time_ms', 'batch_index'])

    features_scaled = scaler.transform(features)
    pred = model.predict(features_scaled)[0]
    score = model.decision_function(features_scaled)[0]

    min_score = score_range['min']
    max_score = score_range['max']
    confidence = (score - min_score) / (max_score - min_score) * 100
    confidence = round(float(np.clip(confidence, 0, 100)), 2)
    is_anomaly = bool(pred == -1)

    recommendation = recommend({
        "status": data.status,
        "response_time_ms": data.response_time_ms,
        "batch_index": data.batch_index,
        "confidence": f"{confidence}%"
    }) if is_anomaly else None

    return {
        "anomaly": is_anomaly,
        "label": "Anomaly" if is_anomaly else "Normal",
        "confidence": f"{confidence}%",
        "details": {
            "status": data.status,
            "response_time_ms": data.response_time_ms,
            "batch_index": data.batch_index
        },
        "recommendation": recommendation
    }