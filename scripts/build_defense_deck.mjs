#!/usr/bin/env node
import pptxgen from "pptxgenjs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Luong Quang Khang";
pptx.subject = "Master thesis defense";
pptx.title = "Evidence-Aware Reinforcement Learning for Traffic Signal Control at a Da Nang Intersection";
pptx.company = "FPT University";
pptx.lang = "en-US";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US",
};
pptx.defineSlideMaster({
  title: "MASTER",
  background: { color: "F5F1E8" },
  objects: [
    { line: { x: 0.58, y: 7.12, w: 12.18, h: 0, line: { color: "CBD2D0", width: 0.6 } } },
    { text: { text: "LUONG QUANG KHANG  |  FPT UNIVERSITY  |  2026", options: { x: 0.62, y: 7.18, w: 7.2, h: 0.18, fontFace: "Aptos", fontSize: 7.5, color: "60706D", margin: 0 } } },
  ],
  slideNumber: { x: 12.35, y: 7.15, w: 0.35, h: 0.2, color: "60706D", fontSize: 8 },
});

const C = { navy: "17324D", coral: "E76F51", teal: "2A9D8F", gold: "E9C46A", ink: "172127", gray: "61706F", paper: "F5F1E8", white: "FFFFFF", pale: "DCE8E5", red: "C94C4C" };
const img = (p) => path.join(ROOT, p);

function title(slide, text, accent = C.coral) {
  slide.addShape(pptx.ShapeType.rect, { x: 0.62, y: 0.48, w: 0.12, h: 0.56, fill: { color: accent }, line: { color: accent } });
  slide.addText(text, { x: 0.92, y: 0.40, w: 11.7, h: 0.72, fontFace: "Aptos Display", fontSize: 29, bold: true, color: C.navy, margin: 0, breakLine: false });
}
function body(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, { x, y, w, h, fontFace: "Aptos", fontSize: opts.fontSize ?? 19, color: opts.color ?? C.ink, margin: opts.margin ?? 0.04, bold: opts.bold ?? false, valign: opts.valign ?? "mid", breakLine: false, fit: "shrink", paraSpaceAfterPt: 6, ...opts });
}
function note(slide, text) { slide.addNotes(text); }
function metric(slide, value, label, x, y, color = C.navy) {
  slide.addText(value, { x, y, w: 2.35, h: 0.62, fontFace: "Aptos Display", fontSize: 31, bold: true, color, margin: 0, align: "center" });
  slide.addText(label, { x, y: y + 0.65, w: 2.35, h: 0.5, fontFace: "Aptos", fontSize: 12.5, color: C.gray, margin: 0.02, align: "center", fit: "shrink" });
}

// 1
{
  const s = pptx.addSlide(); s.background = { color: C.navy };
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.22, h: 7.5, fill: { color: C.coral }, line: { color: C.coral } });
  s.addText("EVIDENCE-AWARE\nREINFORCEMENT LEARNING", { x: 0.85, y: 1.05, w: 8.5, h: 1.5, fontFace: "Aptos Display", fontSize: 35, bold: true, color: C.white, margin: 0, breakLine: false });
  s.addText("Traffic signal control in Da Nang", { x: 0.88, y: 2.75, w: 8.8, h: 0.65, fontSize: 23, color: "D9E3E5", margin: 0 });
  s.addText("Audited junction plus a 53-signal Hai Chau network extension", { x: 0.88, y: 3.54, w: 10.7, h: 0.4, fontSize: 14, color: C.gold, margin: 0 });
  s.addText("Luong Quang Khang\nMaster of Software Engineering\nFPT University · 2026", { x: 0.88, y: 5.35, w: 4.8, h: 1.05, fontSize: 17, color: C.white, margin: 0, breakLine: false });
  s.addText("Supervisors\nDr. Nguyen Luong Vuong\nDr. Bui Cao Vu", { x: 8.6, y: 5.35, w: 3.7, h: 1.05, fontSize: 14, color: "D9E3E5", margin: 0, align: "right", breakLine: false });
}

// 2
{
  const s = pptx.addSlide("MASTER"); title(s, "Research question");
  body(s, "When does a learned controller reduce queue accumulation relative to fixed-time control?", 1.05, 1.5, 11.1, 1.25, { fontSize: 27, bold: true, color: C.navy, align: "center" });
  s.addShape(pptx.ShapeType.line, { x: 2.0, y: 3.15, w: 9.3, h: 0, line: { color: C.teal, width: 2 } });
  metric(s, "53 signals", "Hai Chau network topology", 1.25, 3.65, C.teal);
  metric(s, "30 cases", "9 train · 6 validation · 15 test", 4.05, 3.65, C.coral);
  metric(s, "5 seeds", "fresh gated replay coverage", 6.85, 3.65, C.navy);
  metric(s, "3 regimes", "normal, AM peak, PM peak", 9.65, 3.65, C.gold);
  body(s, "The network evidence is synthetic; the gated result is presentation-ready exploratory evidence.", 1.55, 5.45, 10.2, 0.72, { fontSize: 18, italic: true, color: C.gray, align: "center" });
  note(s, "Research design and scope: thesis_danang.pdf, Chapters 1 and 4.");
}

// 3
{
  const s = pptx.addSlide("MASTER"); title(s, "Evidence boundary");
  s.addImage({ path: img("paper/figures/junction-schematic.png"), x: 0.75, y: 1.32, w: 6.35, h: 4.95 });
  body(s, "Direct evidence", 7.45, 1.45, 4.75, 0.35, { fontSize: 17, bold: true, color: C.teal });
  body(s, "• Published lane description and 103-second program\n• Four camera movement lines on 1 April 2025\n• Twelve aggregate turning movements totaling 6,171 PCU/h", 7.45, 1.86, 4.9, 1.85, { fontSize: 17 });
  body(s, "Model assumptions", 7.45, 4.0, 4.75, 0.35, { fontSize: 17, bold: true, color: C.coral });
  body(s, "• Isolated 300 m approaches\n• Explicit motorcycle and vehicle parameters\n• OSM bearings from a pinned extract", 7.45, 4.42, 4.9, 1.4, { fontSize: 17 });
  body(s, "Demand-matched and geometry-audited", 7.45, 6.0, 4.9, 0.5, { fontSize: 18, bold: true, color: C.navy });
  note(s, "Source: Phan, Le, Nguyen (2025), DOI 10.3390/make7030065. OSM role follows Haklay and Weber (2008), DOI 10.1109/MPRV.2008.80.");
}

// 4
{
  const s = pptx.addSlide("MASTER"); title(s, "Observed demand profile", C.teal);
  s.addImage({ path: img("paper/figures/camera-profile.png"), x: 0.8, y: 1.23, w: 8.25, h: 4.6 });
  metric(s, "1,395", "vehicles at 13:00\nnormal hour", 9.52, 1.55, C.teal);
  metric(s, "2,330", "vehicles at 08:00\nAM peak", 9.52, 3.15, C.coral);
  metric(s, "2,400", "vehicles at 17:00\nPM peak", 9.52, 4.75, C.gold);
  body(s, "Counts cover four digitized camera movement lines. They do not represent the full intersection.", 1.1, 6.15, 10.9, 0.45, { fontSize: 15, italic: true, color: C.gray, align: "center" });
  note(s, "Source: digitized from Figures 17 and 18 in Phan et al. (2025), DOI 10.3390/make7030065. Versioned data: datasets/danang_published/phan2025_camera_hourly_digitized.csv.");
}

// 5
{
  const s = pptx.addSlide("MASTER"); title(s, "Experiment protocol");
  const xs = [0.8, 3.35, 5.9, 8.45, 10.7];
  const labels = [
    ["BUILD", "Published signal\nObserved counts"],
    ["TRAIN", "Five learning seeds\n12 one-hour episodes"],
    ["SELECT", "Validation gates\nfixed-time fallback"],
    ["TEST", "15 matched cases\n3 demand regimes"],
    ["REPORT", "5-seed gate\nCI + limitations"],
  ];
  s.addShape(pptx.ShapeType.line, { x: 1.45, y: 3.0, w: 10.25, h: 0, line: { color: C.navy, width: 3 } });
  labels.forEach((d, i) => {
    s.addShape(pptx.ShapeType.ellipse, { x: xs[i] + 0.55, y: 2.63, w: 0.74, h: 0.74, fill: { color: i === 4 ? C.coral : C.teal }, line: { color: C.paper, width: 2 } });
    body(s, String(i + 1), xs[i] + 0.55, 2.67, 0.74, 0.45, { fontSize: 17, bold: true, color: C.white, align: "center" });
    body(s, d[0], xs[i], 3.63, 1.85, 0.35, { fontSize: 17, bold: true, color: C.navy, align: "center" });
    body(s, d[1], xs[i] - 0.15, 4.1, 2.15, 0.9, { fontSize: 15, color: C.gray, align: "center" });
  });
  body(s, "Independent unit for DDQN: training seed. Matched demand runs stay inside each seed average.", 1.1, 5.72, 11.0, 0.65, { fontSize: 19, bold: true, color: C.navy, align: "center" });
  note(s, "Statistical design follows the few-run cautions in Agarwal et al. (NeurIPS 2021) and Henderson et al. (AAAI 2018).");
}

// 6
{
  const s = pptx.addSlide("MASTER"); title(s, "Controller and safety envelope");
  body(s, "STATE", 0.9, 1.5, 2.25, 0.4, { fontSize: 18, bold: true, color: C.teal, align: "center" });
  body(s, "Approach queues\nPending vehicles\nCurrent phase", 0.9, 2.03, 2.25, 1.4, { fontSize: 19, align: "center" });
  body(s, "DUELING DOUBLE DQN", 4.1, 1.5, 4.4, 0.4, { fontSize: 18, bold: true, color: C.coral, align: "center" });
  body(s, "64 hidden units\nDouble Q target\nThree-step return", 4.1, 2.03, 4.4, 1.4, { fontSize: 19, align: "center" });
  body(s, "ACTION", 9.55, 1.5, 2.3, 0.4, { fontSize: 18, bold: true, color: C.teal, align: "center" });
  body(s, "Choose one of\nthree valid greens", 9.55, 2.03, 2.3, 1.4, { fontSize: 19, align: "center" });
  s.addShape(pptx.ShapeType.chevron, { x: 3.25, y: 2.25, w: 0.6, h: 0.65, fill: { color: C.gold }, line: { color: C.gold } });
  s.addShape(pptx.ShapeType.chevron, { x: 8.72, y: 2.25, w: 0.6, h: 0.65, fill: { color: C.gold }, line: { color: C.gold } });
  s.addShape(pptx.ShapeType.rect, { x: 1.5, y: 4.15, w: 10.3, h: 1.35, fill: { color: C.pale, transparency: 10 }, line: { color: C.teal, width: 1.2 } });
  body(s, "Safety logic stays outside the neural network", 2.0, 4.42, 9.3, 0.38, { fontSize: 21, bold: true, color: C.navy, align: "center" });
  body(s, "20 s minimum green, 7 s clearance, collision output, pending-demand accounting", 2.0, 4.92, 9.3, 0.34, { fontSize: 15.5, color: C.gray, align: "center" });
  body(s, "Reward = −0.01 × (network queue + vehicles waiting to enter)", 2.1, 5.95, 9.1, 0.45, { fontSize: 18, color: C.coral, bold: true, align: "center" });
  note(s, "Methods: Mnih et al. (2015), DOI 10.1038/nature14236; van Hasselt et al. (2016), DOI 10.1609/aaai.v30i1.10295; Wang et al. (2016), PMLR 48.");
}

// 7
{
  const s = pptx.addSlide("MASTER"); title(s, "A held-out collision changed the model", C.red);
  body(s, "The first lane-model protocol used motorcycle τ = 1.0 s.", 0.95, 1.45, 5.6, 0.62, { fontSize: 22, color: C.navy });
  body(s, "AM demand seed 102 produced a rear-end collision at t = 1,762 s.", 0.95, 2.2, 5.8, 0.82, { fontSize: 23, bold: true, color: C.red });
  s.addTable([
    [{ text: "Version", options: { bold: true } }, { text: "Motorcycle τ", options: { bold: true } }, { text: "Held-out collision", options: { bold: true } }, { text: "Decision", options: { bold: true } }],
    ["Superseded", "1.0 s", "1", "Invalidate all runs"],
    ["Final", "1.2 s", "0", "Retrain and retest"],
  ], { x: 6.9, y: 1.45, w: 5.55, h: 2.3, border: { type: "solid", color: "AAB7B4", pt: 1 }, fill: C.white, color: C.ink, fontFace: "Aptos", fontSize: 15, rowH: 0.62, colW: [1.25, 1.25, 1.35, 1.7], margin: 0.08, valign: "mid" });
  s.addShape(pptx.ShapeType.line, { x: 1.0, y: 4.1, w: 11.35, h: 0, line: { color: C.red, width: 1.4 } });
  body(s, "Because headway changes capacity and policy dynamics, the change triggered a complete five-seed rerun.", 1.05, 4.55, 11.15, 1.0, { fontSize: 25, bold: true, color: C.navy, align: "center" });
  body(s, "The failed run remains in the audit trail.", 3.3, 5.85, 6.7, 0.4, { fontSize: 17, italic: true, color: C.gray, align: "center" });
  note(s, "Evidence: results/research_pilot/calibration/tau_sensitivity.json and the full-hour collision regression test.");
}

// 8
{
  const s = pptx.addSlide("MASTER"); title(s, "Learning varies across confirmation seeds");
  s.addImage({ path: img("results/haichau_network_v2/final15-seed-sensitivity.png"), x: 0.8, y: 1.25, w: 8.55, h: 5.05 });
  body(s, "Seed 14", 9.65, 1.55, 2.65, 0.35, { fontSize: 16, bold: true, color: C.gray, align: "center" });
  body(s, "6.12%", 9.65, 2.0, 2.65, 0.65, { fontSize: 32, bold: true, color: C.teal, align: "center" });
  body(s, "largest bounded reduction", 9.65, 2.67, 2.65, 0.6, { fontSize: 13, color: C.gray, align: "center" });
  body(s, "Seed 12", 9.65, 3.55, 2.65, 0.35, { fontSize: 16, bold: true, color: C.gray, align: "center" });
  body(s, "0.78%", 9.65, 4.0, 2.65, 0.65, { fontSize: 32, bold: true, color: C.coral, align: "center" });
  body(s, "AM peak regression", 9.65, 4.67, 2.65, 0.5, { fontSize: 13, color: C.gray, align: "center" });
  body(s, "Seed 15: 0.44% lower. Checkpoint and seed selection remain necessary.", 9.55, 5.55, 2.9, 0.75, { fontSize: 16, bold: true, color: C.navy, align: "center" });
  note(s, "Source: results/haichau_network_v2/final15-three-seed-summary.json and final15-seed-sensitivity.png. This slide motivates the regime gate; the five-seed gated result is reported on slides 9–10.");
}

// 9 native chart
{
  const s = pptx.addSlide("MASTER"); title(s, "Hai Chau bounded result by regime");
  const chart = s.addChart(pptx.ChartType.bar, [
    { name: "Tuned fixed", labels: ["Normal", "AM peak", "PM peak"], values: [1816.83, 2421.85, 4100.74] },
    { name: "Residual DDQN", labels: ["Normal", "AM peak", "PM peak"], values: [1816.83, 2337.65, 3674.77] },
  ], { x: 0.75, y: 1.3, w: 8.4, h: 4.85, catAxisLabelFontFace: "Aptos", catAxisLabelFontSize: 13, valAxisLabelFontFace: "Aptos", valAxisLabelFontSize: 12, showLegend: true, legendFontFace: "Aptos", legendFontSize: 13, legendPos: "b", showTitle: false, showValue: true, dataLabelPosition: "outEnd", chartColors: [C.navy, C.coral], showCatName: false, showValAxisTitle: true, valAxisTitle: "Queue integral (vehicle-hours)", valAxisTitleFontFace: "Aptos", valAxisTitleFontSize: 13, showCatAxisTitle: false, showValue: true, showGridLines: true, gridLine: { color: "D7DEDC", width: 1 }, gapWidthPct: 60, showBorder: false });
  body(s, "0.0%", 9.45, 1.45, 2.75, 0.55, { fontSize: 25, bold: true, color: C.gray, align: "center" });
  body(s, "normal is exactly tied", 9.45, 2.03, 2.75, 0.4, { fontSize: 14, color: C.gray, align: "center" });
  body(s, "3.5% lower", 9.45, 3.0, 2.75, 0.55, { fontSize: 25, bold: true, color: C.teal, align: "center" });
  body(s, "AM peak, seed 14", 9.45, 3.58, 2.75, 0.4, { fontSize: 14, color: C.gray, align: "center" });
  body(s, "10.4% lower", 9.45, 4.55, 2.75, 0.55, { fontSize: 25, bold: true, color: C.teal, align: "center" });
  body(s, "PM peak, seed-14 gate", 9.45, 5.13, 2.75, 0.4, { fontSize: 14, color: C.gray, align: "center" });
  body(s, "Seed-14 raw residual matrix: 8,339.43 → 7,829.25 vehicle-hours (6.12% lower).", 1.1, 6.38, 10.7, 0.35, { fontSize: 13.5, italic: true, color: C.gray, align: "center" });
  note(s, "Chart and PM gate value: results/haichau_network_v2/final15-controller-matrix-summary.json. The interactive demo shows the representative raw residual replay; the gate keeps fixed-time in normal/AM.");
  void chart;
}

// 10
{
  const s = pptx.addSlide("MASTER"); title(s, "Interpretation by regime");
  const rows = [
    ["NORMAL", "Anchored controller reproduces fixed-time exactly", "Keep published plan", C.gray],
    ["AM PEAK", "Seed sensitivity includes regressions", "Use fixed-time gate", C.gold],
    ["PM PEAK", "Residual timing lowers queue in the bounded matrix", "Enable residual policy", C.teal],
  ];
  rows.forEach((r, i) => {
    const y = 1.45 + i * 1.65;
    s.addShape(pptx.ShapeType.line, { x: 0.95, y: y + 1.35, w: 11.35, h: 0, line: { color: "CED5D3", width: 0.8 } });
    body(s, r[0], 1.0, y, 2.0, 0.55, { fontSize: 20, bold: true, color: r[3] });
    body(s, r[1], 3.0, y - 0.03, 5.7, 0.78, { fontSize: 20, color: C.ink });
    body(s, r[2], 9.1, y - 0.03, 3.1, 0.78, { fontSize: 18, bold: true, color: r[3], align: "center" });
  });
  body(s, "Five-seed gate summaries: 1.03–5.62% lower overall (mean 3.48%); normal/AM remain exact fixed-time ties.", 0.55, 6.38, 11.9, 0.42, { fontSize: 17.1, bold: true, color: C.navy, align: "center" });
  note(s, "Sources: final15-regime-gated-direct-multi-seed-summary.json and its hash-bound per-seed summaries. All five seeds now have fresh fifteen-case gate coverage; seeds 13 and 16 use fixed-time normal/AM replays plus residual PM replays. Exploratory gate outside the strict five-seed protocol; case-level regressions remain.");
}

// 11 native line chart
{
  const s = pptx.addSlide("MASTER"); title(s, "Synthetic demand sensitivity", C.teal);
  s.addChart(pptx.ChartType.line, [
    { name: "Published fixed", labels: ["0.75×", "1.00×", "1.25×", "1.50×"], values: [13.95, 79.20, 307.16, 595.67] },
    { name: "Dueling DDQN", labels: ["0.75×", "1.00×", "1.25×", "1.50×"], values: [39.21, 78.41, 159.11, 389.10] },
  ], { x: 0.75, y: 1.25, w: 8.65, h: 5.15, catAxisLabelFontFace: "Aptos", catAxisLabelFontSize: 14, valAxisLabelFontFace: "Aptos", valAxisLabelFontSize: 12, showLegend: true, legendFontFace: "Aptos", legendFontSize: 13, legendPos: "b", showTitle: false, showValue: false, chartColors: [C.navy, C.coral], showValAxisTitle: true, valAxisTitle: "Queue integral (vehicle-hours)", valAxisTitleFontFace: "Aptos", valAxisTitleFontSize: 13, showGridLines: true, gridLine: { color: "D7DEDC", width: 1 }, lineSize: 3, showMarker: true, markerSize: 7, showBorder: false });
  metric(s, "181% worse", "DDQN change\nat 0.75×", 9.65, 1.55, C.red);
  metric(s, "48% lower", "DDQN change\nat 1.25×", 9.65, 3.25, C.teal);
  metric(s, "35% lower", "DDQN change\nat 1.50×", 9.65, 4.95, C.teal);
  body(s, "Legacy single-junction sensitivity; only the 1.00× level is tied to the observed profile.", 1.4, 6.5, 7.6, 0.3, { fontSize: 13.5, italic: true, color: C.gray, align: "center" });
  note(s, "Source: results/danang_protocol_v1/summary/sensitivity-summary.json. This chart is contextual evidence and is separate from the bounded 53-signal network result.");
}

// 12
{
  const s = pptx.addSlide("MASTER"); title(s, "Safety and accounting results");
  metric(s, "6.12%", "queue-hour reduction\nseed-14, 15 cases", 1.0, 1.7, C.teal);
  metric(s, "+1.06 pp", "completion rate\nseed-14 pairs", 4.0, 1.7, C.teal);
  metric(s, "−16.93", "maximum node queue\nvehicles, mean", 7.0, 1.7, C.gold);
  metric(s, "53", "controlled signals\nHai Chau topology", 10.0, 1.7, C.coral);
  s.addShape(pptx.ShapeType.rect, { x: 1.05, y: 4.25, w: 11.2, h: 1.45, fill: { color: C.navy }, line: { color: C.navy } });
  body(s, "Queue metric includes vehicles waiting outside the network", 1.45, 4.55, 10.4, 0.42, { fontSize: 23, bold: true, color: C.white, align: "center" });
  body(s, "scheduled = inserted + pending; inserted = arrived + running", 1.45, 5.08, 10.4, 0.35, { fontSize: 15.5, color: "D9E3E5", align: "center" });
  body(s, "These are bounded synthetic-network outcomes; they do not establish field safety.", 2.35, 6.15, 8.65, 0.4, { fontSize: 17, italic: true, color: C.red, align: "center" });
}

// 13
{
  const s = pptx.addSlide("MASTER"); title(s, "Limits on the claim", C.gold);
  const items = [
    ["ONE DATE", "Departure seeds change timing, not survey days"],
    ["PARTIAL COVERAGE", "Four camera movements do not cover the full junction"],
    ["SYNTHETIC NETWORK", "53 OSM-derived signals, not field-calibrated operation"],
    ["BEHAVIOR ASSUMPTIONS", "No raw headway, queue, or travel-time calibration"],
    ["FIVE TRAINING SEEDS", "Intervals remain wide under sparse traffic"],
  ];
  items.forEach((r, i) => {
    const y = 1.35 + i * 1.03;
    body(s, r[0], 1.0, y, 2.85, 0.45, { fontSize: 16, bold: true, color: i % 2 ? C.coral : C.teal });
    body(s, r[1], 4.0, y - 0.02, 8.1, 0.55, { fontSize: 20, color: C.ink });
  });
  body(s, "Supported conclusion: bounded conditional performance on the Hai Chau simulation network.", 1.25, 6.55, 10.75, 0.36, { fontSize: 18, bold: true, color: C.navy, align: "center" });
}

// 14
{
  const s = pptx.addSlide("MASTER"); title(s, "Defense demo: reliable by design");
  s.addShape(pptx.ShapeType.rect, { x: 0.95, y: 1.4, w: 7.35, h: 4.95, fill: { color: C.navy }, line: { color: C.navy } });
  body(s, "SYNCHRONIZED A/B REPLAY", 1.35, 1.82, 6.55, 0.4, { fontSize: 17, bold: true, color: C.gold, align: "center" });
  body(s, "Published fixed", 1.45, 2.6, 2.75, 0.45, { fontSize: 23, bold: true, color: C.white, align: "center" });
  body(s, "Residual DDQN", 5.05, 2.6, 2.75, 0.45, { fontSize: 23, bold: true, color: C.white, align: "center" });
  s.addShape(pptx.ShapeType.line, { x: 4.62, y: 2.45, w: 0, h: 2.75, line: { color: "7E9497", width: 1.2 } });
  body(s, "Same PM demand\nSame clock\nPhase + queue + arrivals", 1.45, 3.35, 2.75, 1.35, { fontSize: 18, color: "D9E3E5", align: "center" });
  body(s, "Same PM demand\nSame clock\nPhase + queue + arrivals", 5.05, 3.35, 2.75, 1.35, { fontSize: 18, color: "D9E3E5", align: "center" });
  body(s, "No live training", 2.1, 5.52, 5.95, 0.38, { fontSize: 19, bold: true, color: C.coral, align: "center" });
  body(s, "Presentation checklist", 8.85, 1.55, 3.25, 0.35, { fontSize: 19, bold: true, color: C.navy });
  body(s, "1. Run one launcher\n2. Verify offline mode\n3. Use pre-exported replay\n4. Keep video fallback\n5. Keep PDF screenshots", 8.85, 2.08, 3.25, 2.5, { fontSize: 18 });
  body(s, "The bundle is bounded and offline. It illustrates six matched Hai Chau replays.", 8.85, 5.08, 3.25, 1.15, { fontSize: 15, italic: true, color: C.gray });
}

// 15
{
  const s = pptx.addSlide(); s.background = { color: C.navy };
  s.addText("Conclusion", { x: 0.85, y: 0.62, w: 5.0, h: 0.6, fontFace: "Aptos Display", fontSize: 30, bold: true, color: C.gold, margin: 0 });
  s.addText("Residual DDQN helps most in the PM peak on the bounded network matrix.", { x: 0.85, y: 1.55, w: 11.6, h: 1.1, fontFace: "Aptos Display", fontSize: 31, bold: true, color: C.white, margin: 0.02, align: "center", fit: "shrink" });
  s.addShape(pptx.ShapeType.line, { x: 2.0, y: 3.0, w: 9.3, h: 0, line: { color: C.coral, width: 2 } });
  body(s, "Normal", 1.1, 3.55, 2.8, 0.4, { fontSize: 18, bold: true, color: "CFDADC", align: "center" });
  body(s, "Tied", 1.1, 4.05, 2.8, 0.55, { fontSize: 29, bold: true, color: "62C6B7", align: "center" });
  body(s, "AM peak", 5.25, 3.55, 2.8, 0.4, { fontSize: 18, bold: true, color: "CFDADC", align: "center" });
  body(s, "Variable", 5.25, 4.05, 2.8, 0.55, { fontSize: 29, bold: true, color: C.gold, align: "center" });
  body(s, "PM peak", 9.35, 3.55, 2.8, 0.4, { fontSize: 18, bold: true, color: "CFDADC", align: "center" });
  body(s, "10.4% lower", 9.35, 4.05, 2.8, 0.55, { fontSize: 27, bold: true, color: "62C6B7", align: "center" });
  body(s, "Recommendation: preregister the gated campaign, keep fixed-time fallback, and use the offline demo.", 1.3, 5.65, 10.7, 0.62, { fontSize: 20, color: C.white, align: "center" });
  body(s, "Questions and demonstration", 3.35, 6.62, 6.7, 0.4, { fontSize: 18, color: C.gold, bold: true, align: "center" });
}

await pptx.writeFile({ fileName: path.join(ROOT, "presentation/thesis_defense_danang.pptx") });
console.log(path.join(ROOT, "presentation/thesis_defense_danang.pptx"));
