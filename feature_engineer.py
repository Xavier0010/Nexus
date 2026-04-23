# - Libraries -
import pandas as pd
import numpy as np

features = [
    'status',
    'response_time_ms',
    'http_risk_level',
    'is_http_error',
    'rolling_fail_rate',
    'rolling_avg_response_time',
    'response_time_deviation',
    'consecutive_failures'
]

def build_features(df: pd.DataFrame) -> pd.DataFrame:

    # - Functions -
    def http_risk(code: int) -> int:
        if 200 <= code < 300: return 0
        elif 400 <= code < 500: return 1
        elif 500 <= code < 600: return 2
        return 1

    def consecutive_failures(series: pd.Series) -> pd.Series:
        count = 0
        result = []
        for v in series:
            count = count + 1 if int(v) == 0 else 0
            result.append(count)
        return pd.Series(result, index=series.index)


    # - Feature Engineering -
    df = df.copy()
    df = df.sort_values(['id_aplikasi', 'checked_at']).reset_index(drop=True)

    # Encode status
    df['status'] = df['status'].map({'UP': 1, 'DOWN': 0})

    # Change id_service dtype into str
    df['id_service'] = df['id_service'].fillna('monolithic')
    df['id_service'] = df['id_service'].apply(lambda x: str(int(float(x))) if x != 'monolithic' else x)

    # NaN in "response_time_ms", bc of status "DOWN" OR 0
    df.loc[df["status"] == 0, "response_time_ms"] = -1
    df["response_time_ms"] = df["response_time_ms"].fillna(-1).astype(int)

    # HTTP risk
    df['http_risk_level'] = df['http_status_code'].apply(http_risk)
    df['is_http_error'] = (df['http_status_code'] >= 400).astype(int)

    # Failure status
    df['status_fail'] = 1 - df['status']

    # Rolling features
    df['rolling_fail_rate'] = df.groupby('id_service')['status_fail'].transform(lambda x: x.rolling(5, min_periods=1).mean())
    df['rolling_avg_response_time'] = df.groupby('id_service')['response_time_ms'].transform(lambda x: x.rolling(5, min_periods=1).mean())

    # Deviation from baseline
    api_baseline = df.groupby('id_service')['response_time_ms'].transform('mean')
    df['response_time_deviation'] = df['response_time_ms'] - api_baseline

    # Consecutive failures
    df['consecutive_failures'] = df.groupby('id_service')['status'].transform(consecutive_failures)

    return df, df[features]