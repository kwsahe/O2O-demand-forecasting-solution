# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

오늘의집 O2O 서비스팀의 **인테리어 수요 예측 대시보드**.
국토교통부 실거래가(매매/전월세) + 한국부동산원 입주예정물량 + 건축HUB 대수선 이력 +
인테리어 업체/상가 현황 + 행정안전부 인구통계 데이터를 결합해 시군구별(102개)
"인테리어 수요 점수"(0~100점)를 산출하고, Flask 기반 대시보드(4페이지)와
LLM 챗봇(`/api/chat`, `/api/guide-chat`, Ollama)으로 제공한다.

## 아키텍처

- `src/collector.py` — 공공데이터 API 수집기 (매매/전월세 실거래가, 대수선 이력,
  인테리어업체, 소상공인 상가정보 등)
- `src/pipeline.py` — `DemandForecastingPipeline`: 원본 데이터 → 전처리 → 7개 지표
  정규화(Min-Max) → 가중합으로 `인테리어_수요점수` 계산. 인테리어업체수/상가업체수/
  예상시공비/시장규모/인구통계는 가중치에 포함되지 않는 **정보성 컬럼**으로 별도 추가
- `analyze_timeseries.py` — 월별 거래량을 SARIMA/Prophet/LightGBM으로 예측·비교해
  `data/timeseries_forecast_result.json`으로 저장 (`/forecast` 페이지가 읽음)
- `app.py` — Flask 백엔드. 정적 결과 CSV/JSON을 읽어 API로 제공, `/api/chat`·
  `/api/guide-chat`은 Ollama LLM 호출
- `templates/` — 4개 페이지, 전부 순수 HTML/CSS/JS (빌드 도구 없음, CDN으로 Chart.js 로드)
  - `index.html` — 메인 대시보드 (KPI, 차트, 네이버 지도, 랭킹 테이블, 수요 점수 챗봇)
  - `analytics.html` — 통계·분석 (시도별 차트, 인테리어 업체/시장/인구 통계 KPI, 전체 테이블)
  - `forecast.html` — 수요 예측 (SARIMA/Prophet/LightGBM 비교, 모델 설명 카드)
  - `guide.html` — 구매 가이드 (절차 안내 + 가이드 전용 챗봇)
- `data/` — CSV/JSON 결과물 및 원본 데이터. **`.gitignore`로 `data/*.csv`, `data/*.db`,
  `data/_*`가 전부 제외되어 git에는 어떤 데이터 파일도 커밋되지 않음** (코드만 커밋됨).
  원본 CSV는 README의 "데이터 출처" 표 링크에서 직접 받아 `data/`에 넣어야 함

## 개발 시 주의사항

- 새 CSS 변수는 `:root`에 `--xxx` 형태로 추가 (예: `--teal: #2dd4bf`). 4개 템플릿이 각자
  `<style>` 블록을 가지고 있어 CSS 변수/클래스가 중복 정의됨 — 한 페이지를 고치면 동일한
  변경을 나머지 3개 페이지에도 일관되게 적용해야 함 (`nav-link`, `hero-title`,
  `section-label`, `kpi-label` 등 공통 클래스)
- 카드 섹션은 `class="card anim-N"` 패턴 + `grid-column` 인라인 스타일로 배치
- 시군구별 표/데이터에서 "시군구"(개별) 값과 "시도"(합계/평균) 값을 혼동하지 않도록
  주의 — 챗봇 프롬프트에 관련 경고 문구가 있음
- 한글 인코딩: 결과 CSV/JSON은 `utf-8-sig`로 읽고 쓴다. 단, 일부 원본 다운로드 CSV
  (예: 행정안전부 인구통계)는 `cp949`로 제공되므로 로드 시 인코딩을 확인할 것
- Bash 도구의 한글 출력은 터미널 인코딩(cp949) 문제로 깨질 수 있으나 실제 파일은
  정상 UTF-8 (기능 문제 아님). 이 환경의 Bash는 `ls`/`grep`/`wc`/`head` 등 기본 유닉스
  도구가 없을 수 있으니, 파일 목록/검색은 Glob·Grep 도구나 PowerShell을 사용할 것
- **LLM(Ollama, qwen2.5:3b) 사용 시 핵심 원칙**: 작은 로컬 모델에게 표를 직접 읽고
  계산시키면 신뢰도가 낮다(컬럼 혼동, 단위 임의 환산, 멀티턴에서 자기 과거 오답 반복 등
  실제로 겪은 문제들). **숫자 계산/조회는 항상 서버 코드가 미리 끝내서 텍스트로 박아주고,
  LLM에는 "이미 정해진 숫자를 자연어로 설명/포장"만 시킬 것.** 멀티턴 히스토리를 LLM에
  재주입하지 않음(`/api/chat`, `/api/guide-chat` 모두 매 요청이 독립적)

## 알아두면 좋은 과거 이슈

- `src/pipeline.py`의 `extract_sido()`에 `address.spliat()` 오타가 있었음(수정됨) —
  유사한 fallback 경로는 평소 테스트가 안 되니 코드 리뷰 시 주의
- 소상공인 상가정보 API는 "서구"·"남구"·"중구" 등 동명 시군구가 여러 시/도에 존재해
  시군구명만으로 merge하면 데이터가 합쳐지는 버그가 났었음 — 시군구 관련 merge는 항상
  (시도, 시군구) 복합 키를 사용할 것
