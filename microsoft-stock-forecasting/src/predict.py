"""Fetch historical Microsoft prices from FastAPI and forecast the next close."""

import json
from pathlib import Path

import joblib
import pandas as pd
import requests

# Paths and API settings
ROOT = Path(__file__).resolve().parent.parent
API_URL = "http://127.0.0.1:8000/sql/stocks"

# 1. Fetch 100 recent trading records from the API
response = requests.get(API_URL, params={"limit": 100}, timeout=20)
response.raise_for_status()
df = pd.DataFrame(response.json())

if len(df) < 51:
    raise ValueError("The API must return at least 51 trading records.")

# 2. Prepare dates and column names
names = {
    "date": "Date", "open": "Open", "high": "High",
    "low": "Low", "close": "Close", "volume": "Volume"
}
df = df.rename(columns=names)
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date").reset_index(drop=True)

if df["Date"].duplicated().any():
    raise ValueError("Duplicate trading dates found in API data.")
if df[["Date", "Open", "High", "Low", "Close", "Volume"]].isna().any().any():
    raise ValueError("Missing price values found in API data.")
if df["Date"].max() > pd.Timestamp.now():
    raise ValueError("Future-dated test records found. Delete them before forecasting.")

# 3. Recreate the features from Phase 2
df["Year"] = df["Date"].dt.year
df["Month"] = df["Date"].dt.month
df["DayOfWeek"] = df["Date"].dt.dayofweek
df["Daily_Return"] = df["Close"].pct_change(fill_method=None) * 100

for lag in [1, 5, 10]:
    df[f"Close_Lag_{lag}"] = df["Close"].shift(lag)

for window in [7, 20, 50]:
    df[f"MA_{window}"] = df["Close"].rolling(window).mean()

# 4. Load the trained model and its feature list
model = joblib.load(ROOT / "models" / "model.joblib")
features = joblib.load(ROOT / "models" / "feature_columns.joblib")

# Use the latest completed trading session to predict the next one
latest = df.iloc[[-1]][features]
if latest.isna().any().any():
    raise ValueError("The latest row has missing engineered features.")

# 5. Make the forecast
prediction = float(model.predict(latest)[0])
last_date = df["Date"].iloc[-1]
next_date = last_date + pd.offsets.BDay(1)  # Skips weekends, not market holidays

result = {
    "last_trading_date": str(last_date.date()),
    "last_close_usd": round(float(df["Close"].iloc[-1]), 2),
    "estimated_next_trading_date": str(next_date.date()),
    "predicted_close_usd": round(prediction, 2),
    "model": "saved Phase 3 model",
}

print(json.dumps(result, indent=2))

# 6. Save output as evidence for the assignment
output = ROOT / "outputs" / "prediction_result.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"Saved forecast to: {output}")
