import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "/Users/khanglq1/workplace/Thesis/traffic-rl";
const SKILL_DIR = "/Users/khanglq1/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const TMP_DIR = path.join(workspaceDir, "docs/defense/.build-cue-slides");
const FINAL_PPTX = path.join(workspaceDir, "slides/thesis-defense-cue-slides-vi.pptx");
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href
);

const FONT = resolvePresentationFont();
const W = 1280, H = 720;
const C = {
  bg: "#F5F3EC", paper: "#FFFEFA", ink: "#182F4C", body: "#33495F",
  muted: "#657586", teal: "#278F87", coral: "#E76E55", gold: "#D8A938",
  line: "#CBD1D0", paleTeal: "#E3F0ED", paleCoral: "#F8E7E1", paleGold: "#F6EFD9",
  white: "#FFFFFF", slate: "#647585", deep: "#102842",
};
const presentation = Presentation.create({ slideSize: { width: W, height: H } });

function shape(slide, geometry, x, y, w, h, fill = "none", stroke = "none", sw = 0, name) {
  return slide.shapes.add({
    geometry, ...(name ? { name } : {}), position: { left: x, top: y, width: w, height: h }, fill,
    line: { style: "solid", fill: stroke, width: sw },
  });
}
function rect(slide, x, y, w, h, fill, name) { return shape(slide, "rect", x, y, w, h, fill, "none", 0, name); }
function text(slide, value, x, y, w, h, opts = {}) {
  const s = shape(slide, "textbox", x, y, w, h, "none", "none", 0, opts.name);
  s.text = value;
  s.text.style = {
    typeface: opts.font ?? FONT, fontSize: opts.size ?? 24, color: opts.color ?? C.ink,
    bold: opts.bold ?? false, italic: opts.italic ?? false,
    alignment: opts.align ?? "left", verticalAlignment: opts.valign ?? "top",
    autoFit: "shrinkText", wrap: "square", lineSpacing: opts.lineSpacing ?? 1.04,
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return s;
}
function rule(slide, x, y, w, color = C.line, h = 2) { rect(slide, x, y, w, h, color); }
function note(slide, body) { slide.speakerNotes.textFrame.setText(body); }
function base(title, tag, n, footer) {
  const s = presentation.slides.add();
  s.background.fill = C.bg;
  rect(s, 0, 0, 14, H, tag.includes("KẾT QUẢ") ? C.coral : C.teal);
  text(s, tag.toUpperCase(), 72, 30, 760, 28, { size: 17, color: C.teal, bold: true });
  text(s, title, 72, 70, 1125, 72, { size: 43, color: C.ink, bold: true, lineSpacing: 0.98 });
  rule(s, 72, 660, 1136, C.line, 1);
  text(s, footer, 72, 674, 1040, 24, { size: 14, color: C.muted });
  text(s, `${String(n).padStart(2, "0")} / 18`, 1120, 674, 88, 24, { size: 15, color: C.ink, bold: true, align: "right" });
  return s;
}
function dot(slide, x, y, d, color) { shape(slide, "ellipse", x, y, d, d, color); }
function lineArrow(slide, x, y, w, color = C.teal, height = 3) {
  rect(slide, x, y, w - 10, height, color);
  shape(slide, "triangle", x + w - 18, y - 6, 18, 15, color);
}

// 01 — research question
{
  const s = base("Điều khiển thích nghi có giảm hàng chờ?", "Câu hỏi nghiên cứu", 1, "Defense cue deck • theo kịch bản 30 phút, mục 21");
  text(s, "Đánh giá bằng chứng trong mô phỏng ở hai quy mô:", 72, 176, 820, 40, { size: 26, color: C.body });
  text(s, "1 nút giao", 72, 248, 450, 68, { size: 50, bold: true });
  text(s, "53 nút giao", 72, 348, 520, 72, { size: 50, bold: true, color: C.teal });
  rule(s, 72, 330, 630, C.line, 1);
  text(s, "Ba câu cần trả lời", 720, 224, 440, 32, { size: 22, bold: true, color: C.coral });
  text(s, "Khi nào RL giúp?\nSo với baseline nào?\nBằng chứng đủ chắc đến đâu?", 720, 274, 470, 190, { size: 29, color: C.ink, lineSpacing: 1.2 });
  dot(s, 1000, 495, 42, C.coral); dot(s, 1055, 495, 42, C.gold); dot(s, 1110, 495, 42, C.teal);
  text(s, "Claim cuối cùng giới hạn trong phạm vi simulator và các test hiện có.", 72, 548, 1080, 48, { size: 22, color: C.body, italic: true });
  note(s, "Mở đầu bằng câu hỏi nghiên cứu, không mở bằng lời hứa rằng RL luôn tốt hơn. Ba câu hỏi dẫn dắt phần còn lại: lợi ích theo regime, đối chiếu baseline, rồi mức độ tin cậy và giới hạn. Kết quả là bằng chứng mô phỏng, chưa phải hiệu quả ngoài hiện trường.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 21.1; docs/research/thesis-evidence-ledger.md, E11–E15.");
}

// 02 — two experimental layers
{
  const s = base("Hai simulator, hai câu hỏi thực nghiệm", "Thiết kế nghiên cứu", 2, "Không chuyển trọng số giữa SUMO và CityFlow");
  text(s, "SUMO", 80, 190, 470, 72, { size: 51, bold: true });
  text(s, "1 giao lộ", 80, 262, 470, 48, { size: 31, color: C.teal, bold: true });
  text(s, "Có điểm neo dữ liệu công bố\n3 chế độ nhu cầu • 3 pha xanh\nDueling Double DQN", 80, 328, 510, 145, { size: 25, color: C.body, lineSpacing: 1.2 });
  rule(s, 628, 180, 1, C.line, 386);
  text(s, "CityFlow", 690, 190, 500, 72, { size: 51, bold: true });
  text(s, "53 nút điều khiển", 690, 262, 500, 48, { size: 31, color: C.teal, bold: true });
  text(s, "Topology từ OpenStreetMap\nNhu cầu mạng được dựng tổng hợp\nResidual Double DQN", 690, 328, 510, 145, { size: 25, color: C.body, lineSpacing: 1.2 });
  rule(s, 80, 518, 1110, C.ink, 2);
  text(s, "Đọc như hai thí nghiệm bổ sung nhau, không phải một model được phóng từ 1 lên 53 nút.", 80, 542, 1090, 64, { size: 24, color: C.ink, bold: true });
  note(s, "Giải thích ngay từ đầu rằng SUMO và CityFlow dùng hai thiết kế, feature sets, action spaces và model khác nhau. Một giao lộ có empirical anchor ở mức profile nhu cầu công bố; mạng 53 nút có topology OSM nhưng nhu cầu là synthetic. Không nói là transfer learning hay cùng một policy được mở rộng.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 2, 7, 9–10; docs/research/thesis-evidence-ledger.md, E11, E13, E15.");
}

// 03 — data provenance
{
  const s = base("Nguồn dữ liệu: quan sát công bố, không phải trajectory", "Dữ liệu và phạm vi", 3, "Nguồn: paper/figures/camera-profile.png • số liệu số hóa gần đúng");
  const img = new Uint8Array(await fs.readFile(path.join(workspaceDir, "paper/figures/camera-profile.png")));
  s.images.add({ blob: img, contentType: "image/png", alt: "Hồ sơ nhu cầu được số hóa gần đúng từ bốn hướng camera ngày 1/4/2025", fit: "contain", position: { left: 72, top: 175, width: 690, height: 405 } });
  text(s, "01/04/2025", 820, 188, 360, 44, { size: 31, bold: true });
  text(s, "Một ngày\nBốn movement\nCamera đếm tổng hợp", 820, 244, 360, 135, { size: 25, color: C.body, lineSpacing: 1.15 });
  rule(s, 820, 398, 340, C.coral, 3);
  text(s, "Raw video / detector export\nkhông có trong bộ nghiên cứu", 820, 420, 350, 92, { size: 22, color: C.coral, bold: true });
  text(s, "Đường cong là digitization xấp xỉ từ biểu đồ công bố, không phải dữ liệu xe từng giây.", 72, 590, 1090, 48, { size: 21, color: C.body, italic: true });
  note(s, "Nêu rõ provenance: nghiên cứu nguồn báo cáo camera trong một ngày và bốn counting lines/movements. Repo giữ profile đã số hóa từ hình, không có raw video, detector exports hay trajectory. Sai số đọc đồ thị chưa được truyền qua toàn bộ thí nghiệm như một confidence interval. Tránh gọi các route mô phỏng là real trips.\n\nNguồn: paper/figures/camera-profile.png; docs/research/data-feasibility.md; docs/research/danang-data-claim-audit.md; docs/research/thesis-evidence-ledger.md, E01–E06.");
}

// 04 — simulator inputs
{
  const s = base("Từ nguồn dữ liệu đến traffic mô phỏng", "Dữ liệu và phạm vi", 4, "Topology có nguồn; dòng xe toàn mạng là tổng hợp");
  const xs = [92, 455, 818];
  const titles = ["Bản đồ", "Nhu cầu", "Kịch bản"];
  const nums = ["OSM", "Camera profile", "Simulator"];
  const bodies = ["Hình học và kết nối\nđường trong mạng", "Profile công bố được\ndùng để dựng flows", "Tái tạo các case\nđể so sánh policy"];
  for (let i=0;i<3;i++) {
    text(s, String(i+1).padStart(2,"0"), xs[i], 192, 72, 40, { size: 20, color: C.coral, bold: true });
    text(s, titles[i], xs[i], 245, 280, 52, { size: 34, bold: true });
    text(s, nums[i], xs[i], 307, 300, 45, { size: 25, color: C.teal, bold: true });
    text(s, bodies[i], xs[i], 372, 300, 90, { size: 23, color: C.body, lineSpacing: 1.15 });
  }
  lineArrow(s, 345, 330, 82, C.gold); lineArrow(s, 708, 330, 82, C.gold);
  rule(s, 92, 520, 1096, C.line, 1);
  text(s, "Không có dữ liệu thực địa nhiều ngày để xác nhận hiệu quả mạng 53 nút.", 92, 550, 1090, 46, { size: 24, color: C.coral, bold: true });
  note(s, "Đi theo chuỗi: topology từ OSM, nhu cầu được tạo từ các profile công bố, sau đó simulator chạy các case đối chứng. Profile một giao lộ không biến mạng lớn thành quan sát thực địa đã hiệu chỉnh. Hiện chưa có bộ đo nhiều ngày cho hành lang để xác nhận demand và controller toàn mạng.\n\nNguồn: datasets/haichau_network_v2/provenance.json; docs/research/data-feasibility.md; docs/defense/thesis-understanding-guide-vi.md, mục 2, 4, 18.");
}

// 05 — RL loop
{
  const s = base("Vòng lặp RL: quan sát, chọn pha, nhận chi phí", "Phương pháp", 5, "Reward âm queue: ít hàng chờ hơn nghĩa là reward cao hơn");
  const labels = ["Quan sát", "Chọn action", "Mô phỏng", "Reward / update"];
  const desc = ["Features về pha\nvà hàng xe", "Policy chọn trong\ncác action hợp lệ", "Simulator tiến\ntheo thời gian", "Đo queue rồi\ncập nhật Q-value"];
  const xs = [80, 370, 660, 950];
  for (let i=0;i<4;i++) {
    dot(s, xs[i]+80, 190, 64, i===3 ? C.coral : C.teal);
    text(s, String(i+1), xs[i]+80, 204, 64, 34, { size: 26, color: C.white, bold: true, align: "center" });
    text(s, labels[i], xs[i], 284, 224, 45, { size: 27, bold: true, align: "center" });
    text(s, desc[i], xs[i], 345, 224, 82, { size: 22, color: C.body, align: "center", lineSpacing: 1.16 });
    if (i<3) lineArrow(s, xs[i]+205, 222, 74, C.gold, 3);
  }
  rect(s, 80, 500, 1115, 84, C.paleTeal);
  text(s, "Q(s,a)  ≈  reward hiện tại  +  giá trị tương lai", 104, 522, 1050, 44, { size: 30, color: C.ink, bold: true, align: "center" });
  note(s, "Giải thích ngắn: state/observation là tóm tắt, action là lựa chọn điều khiển, reward là chi phí sau khi simulator tiến một đoạn. Q-value ước lượng reward chiết khấu nếu chọn action rồi tiếp tục policy. Reward âm queue khiến ít queue có giá trị cao hơn. Nêu rằng observations là features tóm tắt, không phải toàn bộ trạng thái xe; giả định Markov chỉ là xấp xỉ.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 5–6, 11; src/traffic_rl/agents/dqn.py; src/traffic_rl/agents/schedule_residual.py.");
}

// 06 — Double and Dueling
{
  const s = base("Double DQN và dueling trả lời hai vấn đề khác nhau", "Phương pháp", 6, "SUMO dùng cả hai; CityFlow residual dùng Double DQN, không có dueling heads");
  text(s, "DOUBLE DQN", 88, 195, 470, 44, { size: 21, color: C.teal, bold: true });
  text(s, "Chọn action bằng\nonline network", 88, 252, 490, 90, { size: 34, bold: true });
  lineArrow(s, 88, 375, 112, C.gold);
  text(s, "Đánh giá action đó\nbằng target network", 88, 408, 480, 90, { size: 25, color: C.body });
  rule(s, 633, 180, 1, C.line, 375);
  text(s, "DUELING", 695, 195, 430, 44, { size: 21, color: C.teal, bold: true });
  text(s, "Tách giá trị\ntrạng thái V(s)", 695, 252, 420, 90, { size: 34, bold: true });
  text(s, "+ lợi thế từng action A(s,a)", 695, 364, 450, 42, { size: 25, color: C.body });
  lineArrow(s, 695, 424, 112, C.gold);
  text(s, "Gộp lại thành Q-value", 695, 458, 440, 48, { size: 25, color: C.body });
  text(s, "Một kỹ thuật đổi cách học target; một kỹ thuật đổi kiến trúc output.", 88, 560, 1070, 48, { size: 23, color: C.ink, bold: true });
  note(s, "Double DQN tách chọn action tốt nhất và đánh giá action đó, giảm overestimation do cùng một estimator vừa chọn vừa chấm. Dueling chia state value và action advantage rồi gộp thành Q. Hai kỹ thuật giải quyết khía cạnh khác nhau. SUMO dùng dueling Double DQN; CityFlow residual dùng scalar scoring MLP và Double target nhưng không có V/A heads.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 6, 7.2, 10; src/traffic_rl/agents/dqn.py; src/traffic_rl/agents/phase_ddqn.py.");
}

// 07 — SUMO model
{
  const s = base("SUMO: chọn một trong ba pha xanh mỗi 10 giây", "Mô hình SUMO", 7, "Reward cuối tick là proxy; headline metric được tích phân từng giây");
  const bx = [84, 314, 535, 754, 976];
  const bw = [172, 166, 166, 178, 208];
  const txt = ["16 features", "64 units", "64 units", "V / A heads", "3 Q-values"];
  const fill = [C.paleTeal, C.paper, C.paper, C.paleGold, C.paleTeal];
  for(let i=0;i<5;i++) {
    shape(s,"rect",bx[i],220,bw[i],82,fill[i],i===0||i===4?C.teal:C.line,2);
    text(s,txt[i],bx[i]+5,243,bw[i]-10,38,{size:i===4?24:25,bold:true,align:"center"});
    if(i<4) lineArrow(s,bx[i]+bw[i]+12,260,45,C.gold,2);
  }
  text(s, "Quan sát pha + queue", 86, 337, 270, 36, { size: 21, color: C.body });
  text(s, "Min green 20s • yellow 7s", 385, 337, 410, 36, { size: 22, color: C.body, align: "center" });
  text(s, "Action ở mỗi tick 10s", 857, 337, 340, 36, { size: 22, color: C.body, align: "right" });
  rule(s, 84, 418, 1115, C.line, 1);
  text(s, "Reward", 84, 446, 160, 35, { size: 20, color: C.coral, bold: true });
  text(s, "− queue cuối tick × 0,01", 248, 436, 450, 52, { size: 29, bold: true });
  text(s, "Kiểm tra metric", 84, 518, 190, 35, { size: 20, color: C.teal, bold: true });
  text(s, "Queue được cộng mỗi giây trong cả horizon", 278, 510, 850, 48, { size: 26, color: C.body });
  text(s, "Khác cách lấy mẫu → reward và metric cuối không trùng định nghĩa.", 84, 584, 1100, 40, { size: 21, color: C.coral, italic: true });
  note(s, "State SUMO có 16 features; network 64–64 tách V và A rồi cho ba Q-value, tương ứng ba pha xanh. Agent ra quyết định mỗi 10 giây; môi trường giữ minimum green 20 giây và áp dụng yellow 7 giây khi chuyển. Reward train là âm queue ở cuối tick nhân 0,01; metric báo cáo tích phân queue mỗi giây. Đây là proxy mismatch cần thừa nhận.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 7; configs/danang_pilot.yaml; src/traffic_rl/sim/sumo_single_junction.py; docs/research/thesis-evidence-ledger.md, E11.");
}

// 08 — SUMO training and evaluation
{
  const s = base("SUMO: train theo AM, đánh giá trên ba regime", "Mô hình SUMO", 8, "Test được dùng để sửa tau sau một failure; do đó đây là development-informed test");
  text(s, "30", 78, 192, 190, 100, { size: 84, bold: true, color: C.teal });
  text(s, "episodes / seed", 80, 292, 240, 36, { size: 23, color: C.body });
  text(s, "× 5", 365, 198, 210, 74, { size: 56, bold: true });
  text(s, "learning seeds", 366, 277, 240, 36, { size: 23, color: C.body });
  lineArrow(s, 578, 249, 102, C.gold);
  text(s, "15", 726, 192, 170, 100, { size: 84, bold: true, color: C.teal });
  text(s, "matched test cases", 728, 292, 300, 36, { size: 23, color: C.body });
  text(s, "Normal • AM • PM", 80, 396, 1070, 54, { size: 32, bold: true });
  rule(s, 80, 478, 1110, C.coral, 3);
  text(s, "Checkpoint theo validation; số episode có hạn, chưa chứng minh hội tụ tối ưu.", 80, 505, 1080, 44, { size: 23, color: C.body });
  text(s, "Tái dùng failure test để chỉnh simulator làm yếu tính độc lập của test.", 80, 559, 1080, 44, { size: 22, color: C.coral, bold: true });
  note(s, "Nói rõ 30 episode cho mỗi learning seed, năm learning seeds, một bộ 15 case matched ở Normal/AM/PM. Checkpoint dựa validation chứ không phải minimum training loss. Budget thực nghiệm không chứng minh hội tụ tối ưu. Một held-out failure dẫn đến đổi motorcycle headway tau từ 1,0 lên 1,2 và làm lại các run phụ thuộc; vì vậy test đã thông tin cho quá trình phát triển.\n\nNguồn: docs/research/thesis-evidence-ledger.md, E11; results/research_pilot/calibration/tau_sensitivity.json; docs/defense/thesis-understanding-guide-vi.md, mục 8, 17.");
}

// 09 — schedule residual
{
  const s = base("Residual policy chỉ dịch nhỏ quanh lịch tham chiếu", "Mô hình CityFlow", 9, "Đổi độ linh hoạt lấy phạm vi can thiệp hẹp và dễ kiểm tra hơn");
  text(s, "Lịch cố định", 85, 199, 250, 40, { size: 23, color: C.muted, bold: true });
  const x0=95, y=285, seg=155;
  for(let i=0;i<6;i++) {
    rect(s,x0+i*seg,y,seg-5,72,i%2?C.paleGold:C.paleTeal);
    text(s,`pha ${i+1}`,x0+i*seg,y+20,seg-8,32,{size:21,bold:true,align:"center"});
  }
  text(s,"Request tại boundary 300 giây",95,392,430,38,{size:23,bold:true});
  lineArrow(s,610,410,114,C.gold);
  text(s,"Chọn dịch −10s, 0, hoặc +10s",754,392,420,38,{size:24,color:C.teal,bold:true});
  rule(s,95,484,1080,C.line,1);
  text(s,"Macro 0 = giữ nguyên",95,515,400,44,{size:27,bold:true});
  text(s,"Policy không tự viết lại toàn bộ timing plan.",565,515,610,44,{size:25,color:C.coral,bold:true});
  note(s, "Residual giữ reference schedule làm macro 0. Ở boundary block, policy chọn một request hợp lệ dịch một planned request boundary tối đa ±10 giây; không học lịch tín hiệu hoàn toàn mới. Giới hạn này giúp kiểm tra hành vi và safety contract, nhưng đồng thời giới hạn lợi ích khả dĩ. Không gọi một adjustment mỗi 10 giây: quyết định residual theo block 300 giây.\n\nNguồn: docs/research/haichau-v3b-residual-protocol.md; src/traffic_rl/sim/schedule_residual.py; src/traffic_rl/agents/schedule_residual.py; docs/defense/thesis-understanding-guide-vi.md, mục 9.");
}

// 10 — macro, shadow and anchor
{
  const s = base("Một macro 300 giây; tín hiệu khớp lại ở cuối block", "Mô hình CityFlow", 10, "Anchor chỉ khớp trạng thái tín hiệu; không reset xe hay queue");
  text(s,"0 giây",82,200,130,32,{size:20,color:C.muted,bold:true});
  text(s,"300 giây",1070,200,130,32,{size:20,color:C.muted,bold:true,align:"right"});
  rect(s,105,268,1055,8,C.line);
  for(let i=0;i<=30;i++) {
    const x=105+i*(1055/30);
    rect(s,x,255,i%5===0?3:2,i%5===0?34:19,i===30?C.coral:C.teal);
  }
  text(s,"30 control ticks × 10 giây",210,321,850,38,{size:26,bold:true,align:"center"});
  dot(s,1093,249,28,C.coral);
  rule(s,105,404,1055,C.line,1);
  text(s,"Shadow signal",105,440,310,36,{size:22,color:C.teal,bold:true});
  text(s,"Tính lịch thay thế trong block",105,481,430,70,{size:24,color:C.body});
  text(s,"Anchor",585,440,240,36,{size:22,color:C.coral,bold:true});
  text(s,"Khớp signal state với reference",585,481,550,70,{size:24,color:C.body});
  text(s,"Traffic state vẫn tiếp tục qua boundary.",105,585,1060,38,{size:24,color:C.ink,bold:true});
  note(s, "Mỗi macro kéo dài 300 giây; 30 ticks giả lập/điều khiển 10 giây. Shadow signal thử lịch ứng viên mà chưa thay signal thật. Ở cuối block, anchor đưa trạng thái điều khiển tín hiệu về reference state. Xe, queue, vị trí xe và ảnh hưởng giao thông tiếp tục; anchor không rollback simulator. Đây là lý do điều chỉnh trong block vẫn có thể làm khác kết quả sau đó.\n\nNguồn: src/traffic_rl/sim/schedule_residual.py; docs/research/haichau-v3b-residual-protocol.md; docs/defense/thesis-understanding-guide-vi.md, mục 9.2–9.4.");
}

// 11 — shared policy
{
  const s = base("53 nút dùng chung một MLP chấm macro", "Mô hình CityFlow", 11, "Neighbor features có trong input; kiến trúc không phải GNN");
  text(s,"53",86,205,270,132,{size:112,bold:true,color:C.teal});
  text(s,"nút giao",96,340,240,42,{size:29,bold:true});
  lineArrow(s,345,288,130,C.gold,4);
  text(s,"12 + 12 + 3",520,211,340,68,{size:38,bold:true,align:"center"});
  text(s,"27 features / macro",520,284,340,35,{size:22,color:C.body,align:"center"});
  rect(s,528,348,315,66,C.paper);
  shape(s,"rect",528,348,315,66,"none",C.line,2);
  text(s,"64  →  64  →  1 Q",545,365,280,38,{size:26,bold:true,align:"center"});
  lineArrow(s,870,288,130,C.gold,4);
  text(s,"Một scalar\ncho mỗi macro",1010,232,190,84,{size:26,bold:true,color:C.ink,align:"center"});
  rule(s,86,465,1110,C.line,1);
  text(s,"Không có dueling heads • không có graph message passing",86,493,1110,45,{size:25,color:C.coral,bold:true});
  text(s,"Reward toàn mạng cho 53 nút → credit assignment khó.",86,557,1100,42,{size:23,color:C.body});
  note(s, "Một shared scalar MLP xử lý macro candidates của mọi nút. Mỗi macro có 27 features: 12 source-phase features + 12 target-phase features + 3 macro descriptors. Hidden layers 64 và 64; output scalar Q cho mỗi macro. Có neighbor summaries trong features, nhưng không có GNN/attention/message passing. Reward toàn mạng tạo mục tiêu hợp tác nhưng khó xác định đóng góp action từng nút; chưa chứng minh neighbor feature có lợi nếu thiếu ablation.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 10–11; src/traffic_rl/agents/phase_ddqn.py; docs/research/thesis-evidence-ledger.md, E15.");
}

// 12 — training and selector
{
  const s = base("CityFlow: budget ngắn, chọn checkpoint bằng validation", "Mô hình CityFlow", 12, "Transitions trong cùng episode/block có tương quan; không phải 7.632 mẫu độc lập");
  const blocks=[
    ["12", "episodes × 1h"], ["6", "peak cases"], ["2×", "mỗi case"], ["7.632", "transitions"], ["1.152", "optimizer updates"],
  ];
  const widths=[170,180,155,225,250], gaps=41;
  let x=78;
  for(let i=0;i<blocks.length;i++) {
    text(s,blocks[i][0],x,205,widths[i],74,{size:i===3?47:57,bold:true,color:i===3?C.coral:C.teal,align:"center"});
    text(s,blocks[i][1],x,282,widths[i],48,{size:20,color:C.body,align:"center"});
    x+=widths[i]+gaps;
  }
  rule(s,80,371,1110,C.line,1);
  text(s,"Validation",80,402,220,34,{size:20,color:C.muted,bold:true});
  text(s,"episode 4  →  8  →  12",300,393,830,47,{size:31,bold:true});
  text(s,"Selected",80,474,190,34,{size:20,color:C.teal,bold:true});
  text(s,"3 / 5 seeds",300,465,340,48,{size:31,bold:true});
  text(s,"Seeds 13 và 16 bị reject; chỉ giữ ở mức diagnostic",655,473,515,54,{size:21,color:C.coral,bold:true});
  text(s,"Checkpoint báo cáo seed14 = episode 4",80,554,1090,42,{size:24,color:C.ink});
  note(s, "Nêu con số theo guide: 12 episodes một giờ, sáu peak cases được thấy hai lần, 144 network blocks và budget 7.632 correlated transitions cùng 1.152 optimizer updates. Validation ở episode 4, 8, 12. Selector nhận ba trong năm learning seeds: 12/14/15; 13 và 16 bị reject và nếu nhắc checkpoint của chúng thì gọi diagnostic, không phải eligible. Policy dùng làm headline CityFlow là seed14 episode4. Không suy luận convergence từ loss hay 12 episodes.\n\nNguồn: docs/defense/thesis-understanding-guide-vi.md, mục 12, 16.4; docs/research/evidence-snapshot-2026-09-23/seed14-selection.json; docs/research/thesis-evidence-ledger.md, E14–E15.");
}

// 13 — metrics and comparisons
{
  const s = base("Queue integral đo hàng chờ tích lũy theo thời gian", "Định nghĩa kết quả", 13, "veh-h là vehicle-hours; không phải thời gian chờ trung bình mỗi xe");
  text(s,"queue + due pending",88,194,465,58,{size:33,bold:true});
  text(s,"đo từng giây",88,257,420,38,{size:23,color:C.teal,bold:true});
  lineArrow(s,510,259,110,C.gold,3);
  text(s,"tích phân",652,245,290,54,{size:34,bold:true});
  lineArrow(s,922,259,100,C.gold,3);
  text(s,"veh-h",1050,245,150,54,{size:35,bold:true,color:C.teal});
  rule(s,88,348,1104,C.line,1);
  text(s,"Ví dụ",88,382,180,32,{size:20,color:C.coral,bold:true});
  text(s,"10 xe × 60 giây = 600 xe-giây = 0,167 xe-giờ",88,425,1030,50,{size:28,bold:true});
  text(s,"pending chỉ tính xe đã đến hạn nhưng chưa vào mạng; loại xe chưa phát hành.",88,501,1080,40,{size:21,color:C.body});
  text(s,"Đối chiếu fixed • Max-Pressure • Hysteretic Max-Pressure",88,564,1080,39,{size:22,color:C.ink,bold:true});
  note(s, "Primary metric là tích phân số xe stopped trong network cộng due-but-not-inserted pending, đo mỗi giây rồi chia 3600. Pending chỉ gồm xe đã đến hạn nhưng chưa được đưa vào, không cộng toàn bộ demand tương lai. Queue integral không bằng average per-vehicle delay. CityFlow so với tuned fixed và hai baseline pressure; SUMO còn published fixed. Secondary metrics completion, insertion, travel-time và spillback cần đọc kèm vì giảm queue có thể có trade-off.\n\nNguồn: src/traffic_rl/eval/network_metrics.py; src/traffic_rl/sim/multi_agent_env.py; docs/research/thesis-evidence-ledger.md, E11, E13; docs/defense/thesis-understanding-guide-vi.md, mục 13.");
}

// 14 — SUMO results
{
  const s = base("SUMO: hiệu quả phụ thuộc regime nhu cầu", "Kết quả SUMO", 14, "Δ = learned − published fixed • paired 95% CI trên chênh lệch, đơn vị veh-h");
  const cols=[
    {x:78,name:"NORMAL",pct:"+320,7%",val:"9,86 → 41,50",ci:"Δ 95% CI  [7,60; 56,14]",msg:"xấu hơn rõ",tone:C.coral,pale:C.paleCoral},
    {x:465,name:"AM PEAK",pct:"−1,0%",val:"79,20 → 78,41",ci:"Δ 95% CI  [−9,47; 8,49]",msg:"chưa phân biệt được",tone:C.gold,pale:C.paleGold},
    {x:852,name:"PM PEAK",pct:"−34,5%",val:"152,67 → 99,97",ci:"Δ 95% CI  [−69,55; −35,34]",msg:"giảm hàng chờ",tone:C.teal,pale:C.paleTeal},
  ];
  for(const d of cols) {
    rect(s,d.x,200,328,8,d.tone);
    text(s,d.name,d.x,222,325,30,{size:19,color:d.tone,bold:true});
    text(s,d.pct,d.x,270,325,78,{size:52,bold:true,color:d.tone});
    text(s,d.val,d.x,365,325,34,{size:23,bold:true});
    text(s,d.ci,d.x,419,325,55,{size:18,color:C.body});
    text(s,d.msg,d.x,502,325,45,{size:22,bold:true,color:C.ink});
  }
  rule(s,440,206,1,C.line,360); rule(s,827,206,1,C.line,360);
  text(s,"PM là lợi ích nổi bật; Normal là regression. Không gộp ba regime thành một claim “RL tốt hơn”.",78,586,1110,42,{size:22,color:C.ink,bold:true});
  note(s, "Ba regime trên cùng 15 matched cases, 5 learning seeds; bảng cho mean queue veh-h và relative change. AM gần như bằng fixed nhưng paired 95% interval của chênh lệch chứa 0: không xác lập superiority hay equivalence. PM giảm 34,5%, CI chênh lệch hoàn toàn âm. Normal tăng 320,7%, CI chênh lệch dương. Đây là hiệu quả không đồng đều. Change là phần trăm so với fixed; CI là paired absolute difference, không phải CI phần trăm.\n\nNguồn: docs/research/thesis-evidence-ledger.md, E11; results/danang_protocol_v1/summary/final-summary.json; docs/defense/thesis-understanding-guide-vi.md, mục 15.");
}

// 15 — CityFlow matrix with editable chart
{
  const s = base("CityFlow: residual giảm 6,12%; Max-Pressure giảm nhiều hơn", "Kết quả mạng 53 nút", 15, "15 matched cases × 3.600s • seed14 / episode4 • tổng queue+pending, veh-h");
  const chart = s.charts.add("bar", {
    position: { left: 64, top: 184, width: 760, height: 420 },
    categories: ["Tuned fixed", "Max-Pressure", "Hysteretic MP", "Residual DDQN"],
    series: [{ name: "Queue integral (veh-h)", values: [8339.43,6347.0022,6739.1275,7829.2522], valuesFormatCode: "#,##0", fill: C.teal,
      points: [
        {idx:0,fill:C.slate},{idx:1,fill:C.teal},{idx:2,fill:C.gold},{idx:3,fill:C.coral},
      ] }],
    hasLegend: false,
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 70, varyColors: false },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { typeface: FONT, fontSize: 17, fill: C.ink } },
    xAxis: { min: 0, max: 9000, numberFormatCode: "#,##0", visible: true, textStyle: { typeface: FONT, fontSize: 15, fill: C.body } },
    yAxis: { visible: true, textStyle: { typeface: FONT, fontSize: 17, fill: C.ink } },
    chartFill: "none", plotAreaFill: "none", chartLine: { fill: "none", width: 0 }, plotAreaLine: { fill: "none", width: 0 },
  });
  applyPresentationChartFont(chart,{fontFamily:FONT});
  text(s,"so với tuned fixed",862,205,300,32,{size:20,color:C.muted,bold:true});
  text(s,"−23,89%",862,259,300,54,{size:36,color:C.teal,bold:true});
  text(s,"Max-Pressure",862,311,300,30,{size:21,color:C.body});
  text(s,"−19,19%",862,373,300,54,{size:36,color:C.gold,bold:true});
  text(s,"Hysteretic MP",862,425,300,30,{size:21,color:C.body});
  text(s,"−6,12%",862,487,300,54,{size:36,color:C.coral,bold:true});
  text(s,"Residual DDQN",862,539,300,30,{size:21,color:C.body});
  note(s, "Đọc số CityFlow đúng phạm vi: một policy seed14, checkpoint episode4, trên 15 matched reset one-hour cases. Tổng queue+pending: fixed 8,339.43; Max-Pressure 6,347.00; Hysteretic MP 6,739.13; residual 7,829.25 veh-h. Pooled reduction so với fixed lần lượt 23,89%, 19,19%, 6,12%. Residual tốt hơn fixed trong aggregate này nhưng thua cả hai pressure baselines. Không coi 15 cases là 15 learning seeds hoặc CI policy population.\n\nNguồn: results/haichau_network_v2/final15-controller-matrix-summary.json; docs/research/thesis-evidence-ledger.md, E13; docs/defense/thesis-understanding-guide-vi.md, mục 16.3.");
}

// 16 — PM-only gate and caveat
{
  const s = base("PM-only gate: tín hiệu tích cực nhưng còn hậu nghiệm", "Kết quả và giới hạn", 16, "Gate được chọn sau khi đã xem test; CI không loại bỏ selection bias");
  text(s,"+3,48%",82,205,500,110,{size:77,bold:true,color:C.teal});
  text(s,"trung bình pooled trên 5 seeds",87,315,490,38,{size:22,color:C.body});
  text(s,"95% seed-bootstrap CI",87,378,360,30,{size:19,color:C.muted,bold:true});
  text(s,"[2,01%; 4,95%]",87,416,460,47,{size:30,bold:true});
  rule(s,620,194,1,C.line,360);
  text(s,"PM cases",684,207,430,36,{size:21,color:C.muted,bold:true});
  text(s,"15 cải thiện",684,268,440,48,{size:31,color:C.teal,bold:true});
  text(s,"10 xấu hơn",684,326,440,48,{size:31,color:C.coral,bold:true});
  text(s,"3 / 5 seed được chọn",684,410,465,44,{size:25,bold:true});
  text(s,"seed13, seed16: rejected / diagnostic",684,464,490,55,{size:21,color:C.body});
  rect(s,82,540,1110,63,C.paleCoral);
  text(s,"Cần test mới độc lập; không gọi đây là kết quả xác nhận.",105,556,1060,34,{size:24,color:C.coral,bold:true});
  note(s, "Gate dùng fixed cho normal/AM và residual cho PM; được hình thành sau khi quan sát kết quả regime-specific. Mean 3,48%; bootstrap interval 2,01–4,95% dựa năm seed effects. Trong 25 PM seed-case cells, 15 cải thiện và 10 xấu hơn. 50 Normal/AM cells bằng fixed theo thiết kế. Chỉ 3/5 seeds được selector chọn; seed13 và seed16 là rejected/diagnostic, không tăng eligibility vì gate dương. Vì gate post hoc, CI có điều kiện trên lựa chọn này và không sửa selection bias. Cần test mới với gate/policy khóa trước.\n\nNguồn: docs/research/thesis-evidence-ledger.md, E14; results/haichau_network_v2/final15-regime-gated-direct-multi-seed-summary.json; docs/defense/thesis-understanding-guide-vi.md, mục 16.4.");
}

// 17 — recorded replay
{
  const s = base("Demo là recorded replay, không phải lần chạy simulator mới", "Demo có truy vết", 17, "Visual telemetry 0–1.200s • headline evaluation là horizon riêng 3.600s");
  text(s,"CÙNG CASE PM",82,194,280,31,{size:18,color:C.teal,bold:true});
  text(s,"seed14 • episode4 • demand105 / sim205",82,231,610,34,{size:24,bold:true});
  text(s,"1.085 giây • nút 420249521",82,281,500,34,{size:21,color:C.body});
  text(s,"14",92,354,208,98,{size:73,bold:true,color:C.slate,align:"center"});
  text(s,"fixed • xe đang chờ",92,457,220,44,{size:20,color:C.body,align:"center"});
  text(s,"vs",327,381,80,43,{size:27,color:C.muted,bold:true,align:"center"});
  text(s,"1",436,354,190,98,{size:73,bold:true,color:C.teal,align:"center"});
  text(s,"residual • xe đang chờ",408,457,248,44,{size:20,color:C.body,align:"center"});
  rule(s,705,197,1,C.line,360);
  text(s,"Đọc đúng",758,210,360,36,{size:22,color:C.teal,bold:true});
  text(s,"Một frame minh họa hành vi\ntại một nút và một thời điểm.",758,267,405,92,{size:25,color:C.ink});
  text(s,"Không suy ra 13 xe đã thoát mạng.",758,393,405,70,{size:24,color:C.coral,bold:true});
  text(s,"Kết luận dựa vào bảng aggregate, không dựa screenshot.",82,558,1090,44,{size:23,color:C.ink,bold:true});
  note(s, "Demo bundle phát recorded visual replay; browser không train hoặc chạy một simulator mới. Ví dụ guided frame ở phút 18:05 = 1.085 giây cho node 420249521 trong case PM demand105/sim205; seed14 checkpoint episode4. Hiển thị 14 xe so với 1 xe đang queue. Đây chỉ là snapshot tại một nút/thời điểm; không chứng minh throughput hay toàn mạng. Telemetry demo chỉ có 0–1.200 s, còn metric aggregate lấy từ evaluation horizon riêng 3.600 s.\n\nNguồn: results/haichau_network_v2/demo-visual/index.html; results/haichau_network_v2/demo-visual/manifest.json; docs/defense/demo-runbook.md; docs/defense/thesis-understanding-guide-vi.md, mục 20.");
}

// 18 — conclusion, limits, next work
{
  const s = base("Residual giảm queue nhưng thua Max-Pressure", "Kết luận", 18, "Không suy rộng từ mô phỏng sang hiệu quả thực địa");
  text(s,"Bằng chứng",82,194,280,36,{size:20,color:C.teal,bold:true});
  text(s,"RL giảm queue ở một số regime / case; không đồng đều.",82,243,1080,62,{size:31,bold:true});
  rule(s,82,329,1100,C.line,1);
  text(s,"Giới hạn",82,357,250,35,{size:20,color:C.coral,bold:true});
  text(s,"Dữ liệu mạng tổng hợp • residual thua Max-Pressure • PM gate hậu nghiệm",82,404,1100,48,{size:25,color:C.body});
  rule(s,82,477,1100,C.line,1);
  text(s,"Bước kế",82,502,250,35,{size:20,color:C.gold,bold:true});
  text(s,"Khóa policy và gate → test demand độc lập → bổ sung calibration / ablation",82,549,1100,48,{size:24,bold:true});
  note(s, "Câu chốt khoảng 30 giây: kết quả cho thấy RL có thể giảm hàng chờ ở một số chế độ mô phỏng, nhưng lợi ích không đồng đều và residual hiện tại chưa thắng baseline mạnh nhất ở ma trận 53 nút. Đóng góp là hai lớp thí nghiệm bổ sung nhau, residual policy với hành vi kiểm tra được, và truy vết nguồn/số liệu. Bước tiếp theo là khóa policy và gate trước, test demand mới độc lập, rồi bổ sung calibration thực địa và ablation. Tránh claim deploy hoặc validation field.\n\nNguồn: docs/research/thesis-evidence-ledger.md, E11–E15; docs/research/thesis-review-verification.md; docs/defense/thesis-understanding-guide-vi.md, mục 16.5, 21.5.");
}

if (presentation.slides.items.length !== 18) throw new Error(`Expected 18 slides, got ${presentation.slides.items.length}`);
await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const candidatePath = path.join(TMP_DIR, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const requirements = {
  explicitTotalSlideCount: 18,
  requiredNativeChartOwnerSlides: [15],
  requiredNativeTableOwnerSlides: [],
};
const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: "/Users/khanglq1/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  materializeLiteralChartWorkbooks: true,
  fontPolicy: { basis: "design", families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(TMP_DIR, "validation-v2.json"),
});
console.log(JSON.stringify({ finalPath: FINAL_PPTX, font: FONT, result }, null, 2));
