# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

오늘의집 O2O 서비스팀의 **인테리어 수요 예측 대시보드**.
국토교통부 실거래가(매매/전월세) + 한국부동산원 입주예정물량 + 건축HUB 대수선 이력
데이터를 결합해 시군구별 "인테리어 수요 점수"(0~100점)를 산출하고, Flask 기반
대시보드(`templates/index.html`)와 LLM 챗봇(`/api/chat`, Ollama)으로 제공한다.

## 아키텍처

- `src/collector.py` — 공공데이터 API 수집기 (매매/전월세 실거래가, 대수선 이력 등)
- `src/pipeline.py` — `DemandForecastingPipeline`: 원본 데이터 → 전처리 → 7개 지표
  정규화(Min-Max) → 가중합으로 `인테리어_수요점수` 계산
- `app.py` — Flask 백엔드. 정적 결과 CSV(`data/인테리어_수요점수_결과.csv`,
  `data/시도별_수요집계_요약.csv`)를 읽어 API로 제공, `/api/chat`은 Ollama LLM 호출
- `templates/index.html` — 단일 페이지 대시보드 (KPI 카드, 차트, 랭킹 테이블,
  점수 설명, 챗봇). 순수 HTML/CSS/JS (빌드 도구 없음, CDN으로 Chart.js 로드)
- `data/` — CSV 결과물/원본 수집 데이터 (대부분 `.gitignore` 대상, 결과 CSV는 커밋됨)

## 현재 진행 중인 작업: 네이버 지도 API 연동

지역(시군구)별 수요 점수·지표를 지도 위 마커로 시각화하는 기능 추가.

계획:
1. `data/sigungu_coordinates.csv` — 63개 시군구(서울25/경기29/인천9)의
   중심 좌표(lat/lng) 정적 매핑 테이블 추가
2. `app.py`에 `/api/map-data` 엔드포인트 추가 — 좌표 + `인테리어_수요점수_결과.csv`
   merge해서 반환
3. `templates/index.html`에 지도 카드 섹션 추가 — Naver Maps JS SDK(ncpKeyId)로
   지도를 그리고, 시군구마다 마커를 찍어 수요 점수/등급에 따라 색상 구분,
   클릭 시 인포윈도우로 상세 지표(거래건수/전월세거래건수/수요점수/등급 등) 표시
4. `.env`에 `NAVER_MAP_CLIENT_ID` 추가 (Naver Cloud Platform Maps API 인증키),
   `app.py`에서 `render_template`에 전달해 `index.html`에서 SDK 스크립트 태그에 사용

## 개발 시 주의사항

- 새 CSS 변수는 `:root`에 `--xxx` 형태로 추가 (예: `--teal: #2dd4bf`)
- 카드 섹션은 `class="card anim-N"` 패턴 + `grid-column` 인라인 스타일로 배치
- 시군구별 표/데이터에서 "시군구"(개별) 값과 "시도"(합계/평균) 값을 혼동하지 않도록
  주의 — 챗봇 프롬프트에 관련 경고 문구가 있음
- 한글 인코딩: 모든 CSV는 `utf-8-sig`로 읽고 쓴다
- Bash 도구의 한글 출력은 터미널 인코딩(cp949) 문제로 깨질 수 있으나 실제 파일은
  정상 UTF-8 (기능 문제 아님)
