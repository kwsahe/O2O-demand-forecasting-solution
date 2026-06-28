"""전국 월별 아파트 매매 거래량을 SARIMA/Prophet/LightGBM으로 예측해 비교하고,
결과를 data/timeseries_forecast_result.json으로 저장한다 (대시보드 /forecast 페이지가 읽음).

notebooks/04_TimeSeries_Forecasting.ipynb와 동일한 분석을 스크립트로 실행한다.
"""
import json
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_percentage_error
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
import lightgbm as lgb

df = pd.read_csv("data/raw_api_collected_all.csv", encoding="utf-8-sig", low_memory=False)
df["ym"] = pd.to_datetime(
    df["dealYear"].astype(str) + "-" + df["dealMonth"].astype(str).str.zfill(2) + "-01"
)
monthly = df.groupby("ym").size().rename("y").reset_index().rename(columns={"ym": "ds"})
monthly = monthly[monthly["ds"] < "2026-06-01"].sort_values("ds").reset_index(drop=True)

train = monthly.iloc[:9].copy()
test = monthly.iloc[9:].copy()

# ── SARIMA
sarima_fit = SARIMAX(train["y"], order=(1, 1, 1), seasonal_order=(0, 0, 0, 0)).fit(disp=False)
sarima_pred = sarima_fit.forecast(steps=len(test))
sarima_mape = mean_absolute_percentage_error(test["y"], sarima_pred) * 100

# ── Prophet
prophet_model = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
prophet_model.fit(train[["ds", "y"]])
future = prophet_model.make_future_dataframe(periods=len(test), freq="MS")
forecast = prophet_model.predict(future)
prophet_pred = forecast["yhat"].iloc[-len(test):].values
prophet_mape = mean_absolute_percentage_error(test["y"], prophet_pred) * 100

# ── LightGBM (lag 피처)
full = monthly.copy()
for lag in [1, 2, 3]:
    full[f"lag{lag}"] = full["y"].shift(lag)
full["month"] = full["ds"].dt.month
full_feat = full.dropna().reset_index(drop=True)
train_feat = full_feat[full_feat["ds"] <= train["ds"].max()]
test_feat = full_feat[full_feat["ds"] >= test["ds"].min()]
features = ["lag1", "lag2", "lag3", "month"]
lgb_model = lgb.LGBMRegressor(n_estimators=50, max_depth=3, min_child_samples=1, verbose=-1)
lgb_model.fit(train_feat[features], train_feat["y"])
lgb_pred = lgb_model.predict(test_feat[features])
lgb_mape = mean_absolute_percentage_error(test_feat["y"], lgb_pred) * 100

# ── 결과 JSON 구성
models = {
    "SARIMA": {"mape": round(float(sarima_mape), 2), "predictions": [round(float(v)) for v in sarima_pred]},
    "Prophet": {"mape": round(float(prophet_mape), 2), "predictions": [round(float(v)) for v in prophet_pred]},
    "LightGBM": {"mape": round(float(lgb_mape), 2), "predictions": [round(float(v)) for v in lgb_pred]},
}
best_model = min(models, key=lambda k: models[k]["mape"])

result = {
    "monthly": [
        {"ym": d.strftime("%Y-%m"), "거래건수": int(v)}
        for d, v in zip(monthly["ds"], monthly["y"])
    ],
    "train_months": int(len(train)),
    "test_months": int(len(test)),
    "test_ym": [d.strftime("%Y-%m") for d in test["ds"]],
    "test_actual": [int(v) for v in test["y"]],
    "models": models,
    "best_model": best_model,
}

with open("data/timeseries_forecast_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"[DONE] best_model={best_model}, MAPE={models[best_model]['mape']}%")
print("저장 완료: data/timeseries_forecast_result.json")
