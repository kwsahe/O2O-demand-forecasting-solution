"""5대 광역시(부산/대구/광주/대전/울산) 매매·전월세 실거래가 수집 + 기존 수도권 데이터와 결합해
인테리어 수요 점수 결과를 재생성한다."""

import os
import sys
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(__file__))
load_dotenv()

from src.collector import ApartmentDataCollector, METRO5_SIGUNGU_CODES
from src.pipeline import DemandForecastingPipeline

API_KEY = os.getenv("API_KEY", "")

collector = ApartmentDataCollector(api_key=API_KEY)

print(f"[INFO] 5대 광역시 {len(METRO5_SIGUNGU_CODES)}개 구/군 수집 시작")

df_trade_metro5 = collector.fetch_recent_months(
    sigungu_codes=METRO5_SIGUNGU_CODES,
    months=12,
    save_path="data/raw_api_collected_metro5.csv",
)

df_rent_metro5 = collector.fetch_recent_months_rent(
    sigungu_codes=METRO5_SIGUNGU_CODES,
    months=12,
    save_path="data/raw_rent_collected_metro5.csv",
)

# 기존 수도권 원본 데이터와 결합
df_trade_existing = pd.read_csv("data/raw_api_collected.csv", encoding="utf-8-sig", low_memory=False)
df_trade_all = pd.concat([df_trade_existing, df_trade_metro5], ignore_index=True)
df_trade_all.to_csv("data/raw_api_collected_all.csv", index=False, encoding="utf-8-sig")
print(f"[SAVE] data/raw_api_collected_all.csv ({len(df_trade_all):,}건)")

df_rent_existing = pd.read_csv("data/raw_rent_collected.csv", encoding="utf-8-sig", low_memory=False)
df_rent_all = pd.concat([df_rent_existing, df_rent_metro5], ignore_index=True)
df_rent_all.to_csv("data/raw_rent_collected_all.csv", index=False, encoding="utf-8-sig")
print(f"[SAVE] data/raw_rent_collected_all.csv ({len(df_rent_all):,}건)")

# 파이프라인 재실행 (대수선이력은 수도권 데이터만 존재 -> 5대 광역시는 0으로 처리됨)
pipeline = DemandForecastingPipeline(
    supply_path="data/한국부동산원_주택공급정보_입주예정물량정보_20251231.csv"
)
df_result, sido_summary = pipeline.run(df_transactions=df_trade_all, df_rent=df_rent_all)

df_result.to_csv("data/인테리어_수요점수_결과.csv", index=False, encoding="utf-8-sig")
sido_summary.to_csv("data/시도별_수요집계_요약.csv", index=False, encoding="utf-8-sig")

print(f"\n[DONE] 결과 시군구 수: {len(df_result)}")
print(df_result.head(10).to_string(index=False))
