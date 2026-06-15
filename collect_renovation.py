import os
import sys
import PublicDataReader as pdr
from dotenv import load_dotenv

sys.path.append(".")
from src.collector import (
    ApartmentDataCollector,
    SEOUL_SIGUNGU_CODES,
    GYEONGGI_SIGUNGU_CODES,
    INCHEON_SIGUNGU_CODES,
)

load_dotenv()
API_KEY = os.getenv("API_KEY")

# 법정동 코드 목록 확보 (PublicDataReader, 인증키 불필요)
df = pdr.code_bdong()
df.columns = ["시도코드", "시도명", "시군구코드", "시군구명", "법정동코드",
               "읍면동명", "동리명", "생성일자", "폐지일자"]
df = df[df["폐지일자"].isna() | (df["폐지일자"] == "")]
df = df[df["읍면동명"].astype(str).str.strip() != ""]

all_codes = dict(SEOUL_SIGUNGU_CODES)
all_codes.update(GYEONGGI_SIGUNGU_CODES)
all_codes.update(INCHEON_SIGUNGU_CODES)
target_sigungu = set(all_codes.values())

df = df[df["시군구코드"].astype(str).isin(target_sigungu)]

legal_dong_codes = {}
for sigungu_code, group in df.groupby("시군구코드"):
    legal_dong_codes[sigungu_code] = sorted(group["법정동코드"].astype(str).unique())

total = sum(len(v) for v in legal_dong_codes.values())
print(f"[INFO] 대상 시군구 {len(legal_dong_codes)}개, 총 법정동 {total}개")

collector = ApartmentDataCollector(api_key=API_KEY, request_interval=0.3)
df_all = collector.fetch_renovation_for_region(
    legal_dong_codes,
    save_path="data/raw_renovation_collected.csv",
)
print(f"[DONE] 총 {len(df_all):,}건 수집 완료")
