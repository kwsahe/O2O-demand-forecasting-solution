"""소상공인 상가정보 API로 인테리어 관련 업체 수를 시군구별로 수집하고
인테리어_수요점수_결과.csv에 '소상공인_인테리어업체수' 컬럼을 추가해 재생성한다.

사전 준비: data.go.kr에서 '소상공인시장진흥공단_상가(상권)정보' API 활용신청 후
발급받은 인증키를 .env의 API_KEY 또는 SBIZ_API_KEY로 설정해야 한다.
https://www.data.go.kr/data/15012005/openapi.do
"""

import os
import sys
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(__file__))
load_dotenv()

from src.collector import SmallBusinessCollector
from src.pipeline import DemandForecastingPipeline

API_KEY = os.getenv("SBIZ_API_KEY") or os.getenv("API_KEY", "")

if not API_KEY:
    print("[ERROR] API_KEY 또는 SBIZ_API_KEY가 .env에 없습니다.")
    sys.exit(1)

# ── 1. 파이프라인 재실행하여 기본 결과 CSV 생성
df_trade = pd.read_csv("data/raw_api_collected_all.csv", encoding="utf-8-sig", low_memory=False)
df_rent  = pd.read_csv("data/raw_rent_collected_all.csv", encoding="utf-8-sig", low_memory=False)

pipeline = DemandForecastingPipeline(
    supply_path="data/한국부동산원_주택공급정보_입주예정물량정보_20251231.csv",
    interior_company_path="data/raw_interior_companies.csv",
)
df_result, sido_summary = pipeline.run(df_transactions=df_trade, df_rent=df_rent)

# ── 2. 소상공인 API로 인테리어 관련 업체 수 수집
collector = SmallBusinessCollector(api_key=API_KEY)
sido_sgg_pairs = list(zip(df_result["시도"], df_result["시군구"]))

print(f"\n[INFO] 소상공인 인테리어 업체 수 수집 시작 ({len(sido_sgg_pairs)}개 시군구)")
df_store_counts = collector.fetch_interior_store_counts(sido_sgg_pairs, delay=0.2)

# ── 3. 결과 병합
df_result = df_result.merge(df_store_counts, on=["시도", "시군구"], how="left")
df_result["소상공인_인테리어업체수"] = (
    df_result["소상공인_인테리어업체수"].fillna(0).astype(int)
)

# ── 4. CSV 저장
df_result.to_csv("data/인테리어_수요점수_결과.csv", index=False, encoding="utf-8-sig")
sido_summary.to_csv("data/시도별_수요집계_요약.csv", index=False, encoding="utf-8-sig")

print(f"\n[DONE] 결과 저장 완료 ({len(df_result)}개 시군구)")
top10 = df_result.nlargest(10, "소상공인_인테리어업체수")
print(top10[["시도", "시군구", "소상공인_인테리어업체수", "인테리어_수요점수"]].to_string(index=False))
