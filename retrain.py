import pandas as pd
import numpy as np
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

# Read monitoring_log table (SQL)
df = pd.read_sql()

# Add "http_risk" feature
def http_risk_level(status_code):
    if 200 <= status_code < 300: return 0
    elif 400 <= status_code < 500: return 1
    elif 500 <= status_code < 600: return 2
    return 1

df['http_risk_level'] = df[]