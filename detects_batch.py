import pandas as pd
import numpy as np
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def clean_row(row: dict) -> dict:
    result = {}
    for k, v in row.items():
        if isinstance(v, float) and np.isnan(v):
            result[k] = None
        elif isinstance(v, pd.Timestamp):
            result[k] = v.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(v, np.integer):
            result[k] = int(v)
        elif isinstance(v, np.floating):
            result[k] = float(v)
        else:
            result[k] = v
    return result

df = pd.read_csv('log_monitor.csv')
df['checked_at'] = pd.to_datetime(df['checked_at'])
df['batch_group'] = df['checked_at'].dt.floor('min')

for batch_time, batch_df in df.groupby('batch_group'):
    print(f"\nProcessing batch: {batch_time} ({len(batch_df)} rows)")
    
    batch_df.loc[(batch_df["status"] == "DOWN") & (batch_df["response_time_ms"].isnull()), "response_time_ms"] = -1
    records = [clean_row(r) for r in batch_df.drop(columns=['batch_group']).to_dict(orient='records')]
    payload = {"records": records}

    start = time.perf_counter()
    response = requests.post(f"{BASE_URL}/predict", json=payload)
    elapsed = time.perf_counter() - start

    if response.status_code == 200:
        result = response.json()
        print(f"Total: {result['total']} | Anomalies: {result['anomalies_found']} | Scan time: {elapsed:.2f} sec")
        
        for r in result['result']:
            if r['is_anomaly']:
                print(f"{r['id_aplikasi']} ({r['url']}) -> score: {r['anomaly_score']}")

    else:
        print(f"Error {response.text}")