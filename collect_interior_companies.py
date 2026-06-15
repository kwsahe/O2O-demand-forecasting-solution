"""전국인테리어업체표준데이터를 수집하여 시군구 매칭 컬럼을 포함한 CSV로 저장하고,
인테리어_수요점수_결과.csv에 '인테리어업체수' 컬럼을 채워 재생성한다.

사전 준비: data.go.kr에서 '전국인테리어업체표준데이터' API 활용신청 후 발급받은
인증키를 .env의 API_KEY (또는 INTERIOR_API_KEY)로 설정해야 한다.
"""

import os
import sys
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(__file__))
load_dotenv()

from src.collector import ApartmentDataCollector, INTERIOR_TARGET_SIDO
from src.pipeline import DemandForecastingPipeline

API_KEY = os.getenv("INTERIOR_API_KEY") or os.getenv("API_KEY", "")

collector = ApartmentDataCollector(api_key=API_KEY)

print(f"[INFO] 인테리어업체 데이터 수집 시작 - 대상 시도: {', '.join(INTERIOR_TARGET_SIDO)}")

df_raw = collector.fetch_interior_companies_all(
    ctpv_list=INTERIOR_TARGET_SIDO,
    save_path="data/raw_interior_companies_origin.csv",
)

if df_raw.empty:
    print("[ERROR] 수집된 데이터가 없습니다. API 키/활용신청 상태를 확인하세요.")
    sys.exit(1)

df_norm = collector.normalize_interior_company_columns(df_raw)
matched = df_norm["시군구_코드"].notna().sum()
print(f"[NORMALIZE] 시군구 매칭: {matched:,}/{len(df_norm):,}건")

df_norm.to_csv("data/raw_interior_companies.csv", index=False, encoding="utf-8-sig")
print("[SAVE]    data/raw_interior_companies.csv 저장 완료")

# 기존 수집 원본으로 파이프라인 재실행
df_trade_all = pd.read_csv("data/raw_api_collected_all.csv", encoding="utf-8-sig", low_memory=False)
df_rent_all = pd.read_csv("data/raw_rent_collected_all.csv", encoding="utf-8-sig", low_memory=False)

pipeline = DemandForecastingPipeline(
    supply_path="data/한국부동산원_주택공급정보_입주예정물량정보_20251231.csv"
)
df_result, sido_summary = pipeline.run(df_transactions=df_trade_all, df_rent=df_rent_all)

df_result.to_csv("data/인테리어_수요점수_결과.csv", index=False, encoding="utf-8-sig")
sido_summary.to_csv("data/시도별_수요집계_요약.csv", index=False, encoding="utf-8-sig")

print(f"\n[DONE] 결과 시군구 수: {len(df_result)}")
print(df_result[["시도", "시군구", "인테리어업체수", "인테리어_수요점수"]].head(10).to_string(index=False))
