# API Anomaly Detector

Detects anomalies in API monitoring data using Isolation Forest + LLM recommendations.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file with `GROQ_API_KEY=your_key`
3. Run: `uvicorn api:app --reload`

## Endpoints
- `GET /` - Health check
- `POST /analyze_data` - Detect anomaly and get recommendation with JSON payload {"status": 0 or 1, "response_time_ms": (number), "batch_index": (number)}
