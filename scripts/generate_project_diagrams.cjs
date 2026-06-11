const fs = require("fs");
const path = require("path");
const sharp = require("C:/Users/sangh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/sharp@0.34.5/node_modules/sharp");

const outDir = path.resolve(__dirname, "..", "docs");

function esc(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function wrap(text, max = 18) {
  const words = String(text).split(" ");
  const lines = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > max && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function textBlock(lines, x, y, size = 24, color = "#f8fafc", weight = 700, anchor = "middle") {
  return lines.map((line, i) => (
    `<text x="${x}" y="${y + i * (size + 8)}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}">${esc(line)}</text>`
  )).join("\n");
}

function box({ x, y, w, h, title, body, fill = "#111827", stroke = "#334155", accent = "#38bdf8" }) {
  const bodyLines = Array.isArray(body) ? body : wrap(body, 20);
  return `
    <g>
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="18" fill="${fill}" stroke="${stroke}" stroke-width="2"/>
      <rect x="${x}" y="${y}" width="8" height="${h}" rx="4" fill="${accent}"/>
      ${textBlock([title], x + w / 2, y + 42, 24, "#f8fafc", 800)}
      ${bodyLines.map((line, i) => `<text x="${x + 34}" y="${y + 84 + i * 28}" font-size="19" font-weight="500" fill="#cbd5e1">${esc(line)}</text>`).join("\n")}
    </g>
  `;
}

function arrow(x1, y1, x2, y2, color = "#94a3b8") {
  const mid = (x1 + x2) / 2;
  return `
    <path d="M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2 - 14} ${y2}" fill="none" stroke="${color}" stroke-width="3"/>
    <path d="M ${x2 - 18} ${y2 - 8} L ${x2} ${y2} L ${x2 - 18} ${y2 + 8}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  `;
}

function downArrow(x, y1, y2, color = "#94a3b8") {
  return `
    <path d="M ${x} ${y1} L ${x} ${y2 - 16}" fill="none" stroke="${color}" stroke-width="3"/>
    <path d="M ${x - 8} ${y2 - 18} L ${x} ${y2} L ${x + 8} ${y2 - 18}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  `;
}

function baseSvg(width, height, title, subtitle, content) {
  return `
  <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#08111f"/>
        <stop offset="0.52" stop-color="#101827"/>
        <stop offset="1" stop-color="#172033"/>
      </linearGradient>
      <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
        <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#243449" stroke-width="1" opacity="0.55"/>
      </pattern>
      <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#020617" flood-opacity="0.35"/>
      </filter>
    </defs>
    <rect width="${width}" height="${height}" fill="url(#bg)"/>
    <rect width="${width}" height="${height}" fill="url(#grid)" opacity="0.5"/>
    <text x="70" y="76" font-size="38" font-weight="900" fill="#f8fafc">${esc(title)}</text>
    <text x="72" y="114" font-size="21" font-weight="500" fill="#94a3b8">${esc(subtitle)}</text>
    <g filter="url(#shadow)">
      ${content}
    </g>
    <text x="${width - 70}" y="${height - 36}" font-size="16" font-weight="600" fill="#64748b" text-anchor="end">O2O Demand Forecasting Solution</text>
  </svg>`;
}

function architectureSvg() {
  const content = `
    ${box({ x: 70, y: 170, w: 310, h: 170, title: "데이터 소스", body: ["국토교통부 실거래가 API", "한국부동산원 입주예정 CSV"], fill: "#0f172a", accent: "#f97316" })}
    ${box({ x: 500, y: 150, w: 320, h: 210, title: "수집 계층", body: ["src/collector.py", "requests + XML 파싱", "최근 N개월 자동 수집", "컬럼 정규화"], fill: "#111827", accent: "#38bdf8" })}
    ${box({ x: 940, y: 150, w: 360, h: 210, title: "분석 파이프라인", body: ["src/pipeline.py", "pandas 전처리/집계", "연식 세그먼트 분류", "Min-Max + 가중합 점수"], fill: "#111827", accent: "#34d399" })}
    ${box({ x: 70, y: 460, w: 310, h: 170, title: "저장 데이터", body: ["raw_api_collected.csv", "수요점수 결과 CSV", "시도별 요약 CSV"], fill: "#0f172a", accent: "#a78bfa" })}
    ${box({ x: 500, y: 440, w: 320, h: 210, title: "백엔드 API", body: ["app.py / Flask", "/api/demand", "/api/collect", "/api/search"], fill: "#111827", accent: "#fbbf24" })}
    ${box({ x: 940, y: 440, w: 360, h: 210, title: "대시보드", body: ["templates/index.html", "Chart.js 시각화", "KPI / 랭킹 / 검색", "지역 필터"], fill: "#111827", accent: "#e879f9" })}
    ${arrow(380, 255, 500, 255)}
    ${arrow(820, 255, 940, 255)}
    ${downArrow(225, 340, 460)}
    ${arrow(380, 545, 500, 545)}
    ${arrow(820, 545, 940, 545)}
    ${downArrow(660, 360, 440)}
    ${arrow(1120, 360, 1120, 440)}
  `;
  return baseSvg(
    1368,
    768,
    "프로젝트 구성도",
    "공공데이터 수집부터 수요 점수 산출, Flask API, Chart.js 대시보드까지의 시스템 구조",
    content,
  );
}

function flowSvg() {
  const steps = [
    ["1", "데이터 수집", "실거래가 API와 입주예정 CSV를 확보"],
    ["2", "정제/표준화", "금액·면적·건축연도 숫자화, 지역명 정규화"],
    ["3", "피처 엔지니어링", "연식 계산, 아파트 세그먼트 분류"],
    ["4", "지역 집계", "시도/시군구별 거래건수, 평균금액, 평균연식 집계"],
    ["5", "공급 데이터 결합", "신규 입주 물량을 지역 단위로 LEFT JOIN"],
    ["6", "수요 점수화", "5개 지표 Min-Max 정규화 후 가중합"],
    ["7", "등급/랭킹", "S/A/B 등급과 TOP 지역 랭킹 생성"],
    ["8", "대시보드 제공", "KPI, 차트, 검색, 지역 필터로 시각화"],
  ];

  const boxes = steps.map(([num, title, body], idx) => {
    const col = idx % 4;
    const row = Math.floor(idx / 4);
    const x = 70 + col * 322;
    const y = 172 + row * 255;
    return `
      <g>
        <rect x="${x}" y="${y}" width="272" height="160" rx="18" fill="#111827" stroke="#334155" stroke-width="2"/>
        <circle cx="${x + 42}" cy="${y + 44}" r="23" fill="${idx < 5 ? "#38bdf8" : "#f97316"}"/>
        <text x="${x + 42}" y="${y + 52}" font-size="22" font-weight="900" fill="#08111f" text-anchor="middle">${num}</text>
        <text x="${x + 76}" y="${y + 50}" font-size="23" font-weight="850" fill="#f8fafc">${esc(title)}</text>
        ${wrap(body, 18).map((line, i) => `<text x="${x + 34}" y="${y + 96 + i * 28}" font-size="19" font-weight="500" fill="#cbd5e1">${esc(line)}</text>`).join("\n")}
      </g>
    `;
  }).join("\n");

  const arrows = `
    ${arrow(342, 252, 392, 252)}
    ${arrow(664, 252, 714, 252)}
    ${arrow(986, 252, 1036, 252)}
    <path d="M 1188 332 C 1188 382, 214 382, 214 427" fill="none" stroke="#94a3b8" stroke-width="3"/>
    <path d="M 206 409 L 214 427 L 222 409" fill="none" stroke="#94a3b8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    ${arrow(342, 507, 392, 507)}
    ${arrow(664, 507, 714, 507)}
    ${arrow(986, 507, 1036, 507)}
  `;

  const formula = `
    <g>
      <rect x="270" y="660" width="828" height="52" rx="14" fill="#0f172a" stroke="#25364d" stroke-width="2"/>
      <text x="684" y="694" font-size="20" font-weight="800" fill="#e2e8f0" text-anchor="middle">
        수요점수 = 거래건수 30% + 거래금액 25% + 연식 20% + 면적 15% + 신규입주 10%
      </text>
    </g>
  `;

  return baseSvg(
    1368,
    768,
    "데이터/ML 흐름도",
    "학습형 모델이 아닌 Feature Engineering 기반 수요 점수화 파이프라인",
    `${boxes}${arrows}${formula}`,
  );
}

async function render(name, svg) {
  await fs.promises.mkdir(outDir, { recursive: true });
  const svgPath = path.join(outDir, `${name}.svg`);
  const pngPath = path.join(outDir, `${name}.png`);
  await fs.promises.writeFile(svgPath, svg, "utf8");
  await sharp(Buffer.from(svg)).png().toFile(pngPath);
  return pngPath;
}

async function main() {
  const outputs = [
    await render("project_architecture_diagram", architectureSvg()),
    await render("project_ml_flow_diagram", flowSvg()),
  ];
  console.log(outputs.join("\n"));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
