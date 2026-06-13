from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
import pandas as pd
import os
import sys
import sqlite3
from datetime import datetime
import requests

load_dotenv()

sys.path.append(os.path.dirname(__file__))

from src.collector import ApartmentDataCollector, SEOUL_SIGUNGU_CODES, INCHEON_SIGUNGU_CODES, GYEONGGI_SIGUNGU_CODES
from src.pipeline import DemandForecastingPipeline

app = Flask(__name__)

API_KEY = os.getenv("API_KEY", "")
APT_BASIC_INFO_API_KEY = os.getenv("APT_BASIC_INFO_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:3b")

CHAT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "chat_history.db")


def init_chat_db():
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user_message TEXT NOT NULL,
            bot_answer TEXT,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_chat_log(user_message, bot_answer, status):
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.execute(
        "INSERT INTO chat_logs (created_at, user_message, bot_answer, status) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), user_message, bot_answer, status),
    )
    conn.commit()
    conn.close()


init_chat_db()

print("Flask 앱 초기화 완료")

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/demand", methods=["GET"])
def get_demand():
    try:
        df = pd.read_csv("data/인테리어_수요점수_결과.csv", encoding="utf-8-sig")

        sido = request.args.get("sido", None)
        if sido:
            df = df[df["시도"] == sido]

        top = int(request.args.get("top", 25))
        df = df.head(top)

        return jsonify({
            "status": "ok",
            "count": len(df),
            "data": df.to_dict(orient="records"),
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route("/api/sido-summary", methods=["GET"])
def get_sido_summary():
    try:
        df = pd.read_csv("data/시도별_수요집계_요약.csv", encoding="utf-8-sig")
        return jsonify({
            "status": "ok",
            "count": len(df),
            "data": df.to_dict(orient="records"),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/collect", methods=["POST"])
def collect():
    try:
        body = request.get_json() or {}
        months = int(body.get("months", 12))
        sigungu_code = body.get("sigungu_code", None)

        if not API_KEY:
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."}), 400

        collector = ApartmentDataCollector(api_key=API_KEY)

        if sigungu_code:
            codes = {k: v for k, v in SEOUL_SIGUNGU_CODES.items() if v == sigungu_code}
        else:
            codes = SEOUL_SIGUNGU_CODES

        # 매매 실거래가 수집 & 정규화
        df_raw = collector.fetch_recent_months(
            sigungu_codes=codes,
            months=months,
            save_path="data/raw_api_collected.csv"
        )
        df_normalized = collector.normalize_columns(df_raw)

        # 전월세 실거래가 수집 & 정규화
        df_rent_raw = collector.fetch_recent_months_rent(
            sigungu_codes=codes,
            months=months,
            save_path="data/raw_rent_collected.csv"
        )
        df_rent_normalized = (
            collector.normalize_rent_columns(df_rent_raw) if not df_rent_raw.empty else None
        )

        # 파이프라인 실행
        pipeline = DemandForecastingPipeline(
            supply_path="data/한국부동산원_주택공급정보_입주예정물량정보_20251231.csv"
        )
        df_result, sido_summary = pipeline.run(df_transactions=df_normalized, df_rent=df_rent_normalized)

        # 결과 저장
        df_result.to_csv("data/인테리어_수요점수_결과.csv", index=False, encoding="utf-8-sig")
        sido_summary.to_csv("data/시도별_수요집계_요약.csv", index=False, encoding="utf-8-sig")

        return jsonify({
            "status": "ok",
            "collected": len(df_raw),
            "top5": df_result.head(5).to_dict(orient="records"),
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route("/api/search", methods=["GET"])
def search():
    try:
        q = request.args.get("q", "")
        search_type = request.args.get("type", "region")

        if not q:
            return jsonify({"status": "error", "message": "검색어를 입력하세요."}), 400

        if search_type == "apt":
            # 단지명 검색 — 원본 데이터에서 검색
            df = pd.read_csv("data/raw_api_collected.csv", encoding="utf-8-sig")
            mask = df["aptNm"].str.contains(q, na=False)
            df_filtered = df[mask][["aptNm", "umdNm", "dealAmount", "buildYear", "excluUseAr", "dealYear", "dealMonth"]].copy()
            df_filtered.columns = ["단지명", "법정동", "거래금액_만원", "건축년도", "전용면적", "년", "월"]
            df_filtered = df_filtered.head(50)
        else:
            # 지역 검색 — 수요 점수 결과에서 검색
            df = pd.read_csv("data/인테리어_수요점수_결과.csv", encoding="utf-8-sig")
            mask = (
                df["시도"].str.contains(q, na=False) |
                df["시군구"].str.contains(q, na=False)
            )
            df_filtered = df[mask]

        return jsonify({
            "status": "ok",
            "query": q,
            "type": search_type,
            "count": len(df_filtered),
            "data": df_filtered.to_dict(orient="records"),
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 챗봇 메시지에서 단지명/주소(법정동)를 인식할 때 무시할 일반 단어
CHAT_STOPWORDS = {
    "수요", "점수", "지역", "시군구", "아파트", "단지", "거래", "거래금액", "건축년도",
    "전용면적", "가격", "시세", "노후도", "등급", "설명", "알려줘", "가르쳐줘", "어디",
    "얼마", "얼마나", "어떻게", "무엇", "뭐야", "뭐예요", "궁금해", "정보", "최근",
    "그리고", "그럼", "그래서", "에서", "에게", "에는", "으로", "한테", "대해",
}

def find_apartment_context(message: str, raw_path: str = "data/raw_api_collected.csv", limit: int = 10) -> str:
    """메시지에 포함된 단지명/법정동 키워드로 원본 실거래 데이터를 검색해 컨텍스트 문자열을 만든다.
    공백 차이나 약간의 오타가 있어도 인식할 수 있도록 정규화 매칭과 유사도 매칭을 함께 사용한다."""
    if not os.path.exists(raw_path):
        return ""

    import re
    from difflib import get_close_matches

    tokens = {t for t in re.split(r"[^\w가-힣]+", message) if len(t) >= 2 and t not in CHAT_STOPWORDS}
    if not tokens:
        return ""

    try:
        df = pd.read_csv(raw_path, encoding="utf-8-sig", low_memory=False)
    except Exception:
        return ""

    apt_names = df["aptNm"].astype(str)
    umd_names = df["umdNm"].astype(str)

    # 1) 부분 문자열 매칭 — 공백을 제거하고 비교해 "래미안 서초"/"래미안서초" 같은 표기 차이를 흡수
    norm_apt = apt_names.str.replace(r"\s+", "", regex=True)
    norm_umd = umd_names.str.replace(r"\s+", "", regex=True)

    mask = pd.Series(False, index=df.index)
    matched_any = False
    for token in tokens:
        norm_token = re.sub(r"\s+", "", token)
        m = (
            norm_apt.str.contains(norm_token, na=False, regex=False) |
            norm_umd.str.contains(norm_token, na=False, regex=False)
        )
        if m.any():
            matched_any = True
        mask |= m

    # 2) 부분 문자열 매칭이 실패하면 — 오타·유사 표기를 허용하는 유사도 매칭(difflib)
    if not matched_any:
        unique_apts = apt_names.unique().tolist()
        unique_umds = umd_names.unique().tolist()
        for token in tokens:
            for name in get_close_matches(token, unique_apts, n=3, cutoff=0.6):
                mask |= (apt_names == name)
            for name in get_close_matches(token, unique_umds, n=3, cutoff=0.6):
                mask |= (umd_names == name)

    matched = df[mask]
    if matched.empty:
        return ""

    cols = ["aptNm", "umdNm", "dealAmount", "buildYear", "excluUseAr", "dealYear", "dealMonth"]
    matched = matched[cols].copy()
    matched.columns = ["단지명", "법정동", "거래금액_만원", "건축년도", "전용면적_m2", "년", "월"]
    matched = matched.sort_values(["년", "월"], ascending=False).head(limit)

    return (
        "\n\n[질문과 관련된 단지 최근 실거래 내역 (국토교통부 실거래가 데이터)]\n"
        + matched.to_csv(index=False)
    )

def find_region_context(message: str, df: pd.DataFrame, sido_summary: pd.DataFrame) -> str:
    """메시지에 언급된 시군구/시도를 찾아 해당 행만 따로 추려 컨텍스트로 제공한다.
    전체 표를 한꺼번에 주면 작은 모델이 시도 합계와 시군구 개별값을 혼동하므로,
    질문 대상 지역의 정확한 행을 별도로 강조해 전달한다."""
    import re

    tokens = {t for t in re.split(r"[^\w가-힣]+", message) if len(t) >= 2 and t not in CHAT_STOPWORDS}
    if not tokens:
        return ""

    sigungu_mask = pd.Series(False, index=df.index)
    sido_mask = pd.Series(False, index=sido_summary.index)
    for token in tokens:
        sigungu_mask |= df["시군구"].str.contains(token, na=False)
        sido_mask |= sido_summary["시도"].str.contains(token, na=False)

    parts = []
    matched_sigungu = df[sigungu_mask]
    if not matched_sigungu.empty:
        parts.append(
            "[질문에 언급된 시군구의 정확한 데이터 — 시군구 단위 질문에는 반드시 이 표의 값을 사용하세요]\n"
            + matched_sigungu.to_csv(index=False)
        )

    matched_sido = sido_summary[sido_mask]
    if not matched_sido.empty:
        parts.append(
            "[질문에 언급된 시/도의 전체 요약 데이터 — 시/도 전체 합계·평균값이며, 개별 시군구의 값이 아닙니다]\n"
            + matched_sido.to_csv(index=False)
        )

    if not parts:
        return ""
    return "\n\n" + "\n\n".join(parts)


def get_recent_chat_history(limit: int = 3):
    """최근 대화 기록을 가져와 멀티턴 대화(이어지는 질문)를 지원한다."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    rows = conn.execute(
        "SELECT user_message, bot_answer FROM chat_logs WHERE status = 'ok' ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return list(reversed(rows))


@app.route("/api/chat", methods=["POST"])
def chat():
    message = ""
    try:
        body = request.get_json() or {}
        message = body.get("message", "").strip()

        if not message:
            return jsonify({"status": "error", "message": "메시지를 입력하세요."}), 400

        df = pd.read_csv("data/인테리어_수요점수_결과.csv", encoding="utf-8-sig")
        df = df.sort_values("인테리어_수요점수", ascending=False)
        sido_summary = pd.read_csv("data/시도별_수요집계_요약.csv", encoding="utf-8-sig")

        system_prompt = (
            "당신은 '오늘의집 O2O 인테리어 수요 예측 대시보드'의 친절한 데이터 분석 도우미입니다. "
            "항상 따뜻하고 다정한 말투로, 처음 보는 사람도 이해할 수 있도록 쉽게 풀어서 한국어로 답변하세요. "
            "숫자만 툭 던지지 말고, 그 숫자가 어떤 의미인지, 왜 그런지까지 함께 설명해주세요. "
            "지역별 수치를 묻는 질문은 아래 CSV 데이터를 근거로 답하고, "
            "'인테리어 수요 점수가 무엇인지/어떻게 계산되는지' 같은 질문은 아래 [인테리어 수요 점수 산출 방식] 설명을 활용해 "
            "단계별로 자세하고 친절하게 설명하세요. "
            "사용자가 특정 아파트 단지명이나 주소(법정동)를 언급하면, 아래 [질문과 관련된 단지 최근 실거래 내역]을 참고해 "
            "해당 단지의 최근 거래금액, 건축년도, 전용면적 등 정보를 알려주세요. "
            "필요하면 예시를 들어 설명하고, 적절히 이모지를 곁들여도 좋습니다. "
            "데이터에 없는 내용은 추측하지 말고 모른다고 솔직하게 답하세요.\n\n"
            "[매우 중요 — 표 혼동 금지 규칙]\n"
            "이 시스템에는 두 종류의 표가 있습니다. 절대 서로 혼동하지 마세요.\n"
            "  1) [시군구별 인테리어 수요 점수]: '시군구'(예: 서울특별시 서초구) 단위의 개별 데이터입니다. "
            "사용자가 특정 시(군/구) 이름을 언급하면 반드시 이 표에서 해당 행만 찾아 답하세요.\n"
            "  2) [시도별 요약]: '시도'(서울/경기/인천 등) 전체의 합계·평균·최고값입니다. "
            "이 값들은 그 시/도에 속한 여러 시군구를 모두 합치거나 평균낸 값이므로, "
            "개별 시군구(예: 서초구)의 거래건수나 점수로 절대 사용하면 안 됩니다. "
            "예를 들어 '서울'의 총거래건수·총신규입주세대수는 서울 전체 25개 구의 합계이며, "
            "'서초구' 한 곳의 값이 아닙니다.\n"
            "  3) 만약 아래에 [질문에 언급된 시군구의 정확한 데이터] 또는 [질문에 언급된 시/도의 전체 요약 데이터] 블록이 있다면, "
            "그 블록의 값을 최우선으로 사용하세요.\n\n"
            "[인테리어 수요 점수 산출 방식]\n"
            "아파트 실거래 데이터를 분석해 '어느 지역에 인테리어 수요가 얼마나 있는가'를 0~100점으로 수치화한 지표입니다. "
            "점수가 높을수록 리모델링 수요가 많고, 구매력이 높고, 거래가 활발한 지역입니다.\n\n"
            "1단계. 핵심 타겟 아파트 추출 — 건축연식(노후도)에 따라 4단계로 분류하고, "
            "15~20년 된 'Old_Apartment'만 분석 대상으로 삼습니다.\n"
            "  - New_Apartment (0~5년): 가구·소품 인테리어 수요\n"
            "  - Mid_Apartment (6~14년): 벽지·바닥재 부분 교체 수요\n"
            "  - Old_Apartment ★ (15~20년, 핵심 타겟): 욕실·주방·바닥재 등 전면 리모델링 수요. "
            "1기 신도시 재정비 연식대와 겹쳐 리모델링 관심이 가장 높고 고단가 시공 상품 구매 가능성이 높음\n"
            "  - Very_Old_Apartment (21년+): 재건축 검토 단계, 인테리어 시공 수요 낮음\n\n"
            "2단계. 6가지 지표를 0~100점으로 정규화(Min-Max) 후 가중치를 곱해 합산\n"
            "  - 거래건수 (가중치 25%): 매매 시장 활성도, 도달 가능 고객 수\n"
            "  - 거래금액 (가중치 20%): 구매력, 고단가 시공 가능성\n"
            "  - 노후도 (가중치 15%): 리모델링 시급성\n"
            "  - 전용면적 (가중치 10%): 시공 규모, 매출 기여도\n"
            "  - 신규입주 (가중치 10%): 신규 입주 세대의 인테리어 수요\n"
            "  - 전월세거래건수 (가중치 20%): 임대(전월세) 거래가 많을수록 새 세입자가 입주 전 부분 인테리어를 하는 수요가 많음\n\n"
            "3단계. 최종 점수 계산식\n"
            "  인테리어_수요점수 = 거래건수점수×0.25 + 거래금액점수×0.20 + 노후도점수×0.15 + 면적점수×0.10 "
            "+ 신규입주점수×0.10 + 전월세거래건수점수×0.20\n\n"
            "등급 해석\n"
            "  - S등급 (60~100점): 최우선 타겟, 마케팅 예산 집중\n"
            "  - A등급 (30~59점): 중간 타겟, 선별적 마케팅\n"
            "  - B등급 (0~29점): 관찰 지역, 투자 보류\n\n"
            "[데이터 컬럼 설명 — 시군구별 표]\n"
            "- 인테리어_수요점수: 위 산출 방식으로 계산된 0~100점 값 (해당 시군구 자체의 점수)\n"
            "- 거래건수: 해당 시군구의 노후도 15~20년(Old_Apartment) 세그먼트 거래 건수\n"
            "- 평균거래금액_만원 / 평균노후도_년 / 평균면적_m2: 해당 시군구 Old_Apartment 평균값\n"
            "- 신규입주_세대수 / 입주단지수: 해당 시군구의 입주예정 신규 세대수 / 단지 수\n"
            "- 전월세거래건수: 해당 시군구의 노후도 15~20년(Old_Apartment) 세그먼트 전월세 거래 건수\n\n"
            "[데이터 컬럼 설명 — 시도별 요약 표]\n"
            "- 시군구수: 해당 시/도에 속한 시군구의 개수\n"
            "- 총거래건수: 해당 시/도에 속한 모든 시군구 거래건수의 합계\n"
            "- 평균수요점수 / 최고수요점수: 해당 시/도에 속한 시군구들의 인테리어_수요점수 평균값 / 최고값\n"
            "- 총신규입주세대수: 해당 시/도에 속한 모든 시군구 신규입주_세대수의 합계\n\n"
            "[시군구별 인테리어 수요 점수 (수요 점수 높은 순)]\n"
            f"{df.to_csv(index=False)}\n"
            "[시도별 요약]\n"
            f"{sido_summary.to_csv(index=False)}"
            f"{find_region_context(message, df, sido_summary)}"
            f"{find_apartment_context(message)}\n\n"
            "반드시 한국어로만 답변하세요. 다른 언어(영어, 중국어, 일본어 등)는 절대 사용하지 마세요."
        )

        messages = [{"role": "system", "content": system_prompt}]
        for past_user, past_answer in get_recent_chat_history():
            messages.append({"role": "user", "content": past_user})
            messages.append({"role": "assistant", "content": past_answer})
        messages.append({"role": "user", "content": message})

        res = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": CHAT_MODEL,
                "messages": messages,
                "stream": False,
            },
            timeout=120,
        )
        res.raise_for_status()
        answer = res.json()["message"]["content"]

        save_chat_log(message, answer, "ok")
        return jsonify({"status": "ok", "answer": answer})

    except requests.exceptions.ConnectionError:
        save_chat_log(message, None, "error: ollama_connection")
        return jsonify({"status": "error", "message": f"Ollama 서버({OLLAMA_HOST})에 연결할 수 없습니다."}), 500
    except Exception as e:
        save_chat_log(message, None, f"error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",  # 외부 접속 허용 (배포 시 필요)
        port=5000,
        debug=True,      # 코드 변경 시 자동 재시작
    )