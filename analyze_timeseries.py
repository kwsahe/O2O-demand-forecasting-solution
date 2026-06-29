"""전국 월별 아파트 매매 거래량을 SARIMA/Prophet/LightGBM으로 예측해 비교하고,
결과를 data/timeseries_forecast_result.json으로 저장한다 (대시보드 /forecast 페이지가 읽음).

notebooks/04_TimeSeries_Forecasting.ipynb와 동일한 분석을 스크립트로 실행한다.
마지막 단계에서 로컬 LLM(Ollama)에게 이미 계산된 숫자만 주고 "AI 판단 결과" 문단을
한 번 생성해 JSON에 캐싱한다 (페이지 로드마다 LLM을 부르면 느리고 불안정해서, 이 스크립트를
재실행할 때만 갱신).
"""
import os
import json
import warnings
warnings.filterwarnings("ignore")

import requests
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_percentage_error
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
import lightgbm as lgb

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:3b")

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


def generate_ai_judgment(monthly, train, test, models, best_model):
    """이미 계산된 숫자만 프롬프트에 넣어 LLM이 그 숫자를 자연어로 설명/판단하게 한다.
    LLM에게 계산을 시키지 않는다 — 트렌드 해석과 신뢰도 평가만 맡긴다."""
    monthly_text = "\n".join(f"{r.ds.strftime('%Y-%m')}: {int(r.y):,}건" for r in monthly.itertuples())
    model_text = "\n".join(
        f"- {name}: MAPE {info['mape']}% (검증 구간 예측값 {info['predictions']})"
        for name, info in models.items()
    )

    prompt = (
        "당신은 부동산 거래량 시계열 예측 결과를 해설하는 분석가입니다. "
        "아래 [확정된 데이터]에 있는 숫자만 사용하세요. 새로운 숫자를 계산하거나 추측해서 "
        "만들어내지 마세요 — 추세 해석과 신뢰도 평가만 한국어 3~5문장으로 작성하세요.\n\n"
        "[확정된 데이터]\n"
        f"전국 월별 아파트 매매 거래건수 (학습 {len(train)}개월 + 검증 {len(test)}개월):\n"
        f"{monthly_text}\n\n"
        f"검증 구간 실제 거래건수: {[int(v) for v in test['y']]}\n\n"
        f"모델별 예측 정확도(MAPE, 낮을수록 정확):\n{model_text}\n\n"
        f"최우수 모델: {best_model} (MAPE {models[best_model]['mape']}%)\n\n"
        "위 데이터만 근거로: (1) 최근 거래량 추세가 상승/하락/혼조 중 무엇인지, "
        f"(2) {best_model}이 왜 가장 신뢰할 수 있는지, (3) 데이터가 11개월뿐이라 "
        "계절성 판단에 한계가 있다는 점을 반드시 포함해 짧게 답변하세요. "
        "반드시 한국어로만 답변하세요."
    )

    try:
        res = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_ctx": 4096, "num_predict": 512},
            },
            timeout=120,
        )
        res.raise_for_status()
        return res.json()["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        print(f"[WARNING] AI 판단 결과 생성 실패 (Ollama 연결 불가): {e}")
        return None


ai_judgment = generate_ai_judgment(monthly, train, test, models, best_model)

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
    "ai_judgment": ai_judgment,
}

with open("data/timeseries_forecast_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"[DONE] best_model={best_model}, MAPE={models[best_model]['mape']}%")
print(f"[AI 판단 결과] {'생성됨' if ai_judgment else '생성 실패 (Ollama 미실행?)'}")
print("저장 완료: data/timeseries_forecast_result.json")
