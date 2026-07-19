(function () {
  "use strict";
  const RAB = window.ReplayAB, R3 = window.Replay3D;

  const SCENARIOS = [
    ["haichau_rush", "Cao điểm thực (rush)"],
    ["danang_peak", "Đà Nẵng peak"],
    ["haichau_peak", "Cao điểm quá tải (peak)"],
    ["haichau", "Quá tải nặng (haichau)"],
  ];
  const DEFAULT_SCENARIO = "haichau_rush";
  const CTRLS = [["fixed_time", "Cố định (Fixed-Time)"], ["dqn", "RL (DQN)"],
                 ["max_pressure", "Max-Pressure"], ["random", "Ngẫu nhiên"]];
  const CTRL_TO_ROW = { dqn: "DQN", fixed_time: "FixedTime",
                        max_pressure: "MaxPressure", random: "Random" };
  const ROADNET = (sc) => `/data/danang/replay_roadnet_${sc}.json`;
  const REPLAY = (sc, c) => `/results/${sc}/demo/replay_${c}_demo.txt`;
  const COMPARISON = (sc) => `/results/${sc}/comparison.json`;
  const CAR_COLORS = [[242, 191, 215], [183, 235, 228], [219, 235, 183],
                      [245, 221, 181], [212, 181, 245]];
  const DT = 10; // seconds of sim time per replay frame (action interval)

  const S = {
    scenario: DEFAULT_SCENARIO,
    ctrls: { left: "fixed_time", right: "dqn" },
    roadnet: null, comparison: null,
    steps: { left: [], right: [] },
    T: 0, playing: false, timer: null, gen: 0,
  };
  const decks = {};
  let viewState = null, fitState = null;

  const $ = (id) => document.getElementById(id);
  function fetchText(u) {
    return fetch(u).then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status + " " + u);
      return r.text();
    });
  }
  function ctrlLabel(key) {
    for (const [k, label] of CTRLS) if (k === key) return label;
    return key;
  }

  // ---------- layers ----------
  function roadLayer(roadnet) {
    return new deck.PathLayer({
      id: "roads",
      data: roadnet.roads,
      getPath: (r) => r.points.map((p) => [p.x, p.y]),
      getWidth: (r) => r.nLanes * 3,
      widthUnits: "meters",
      widthMinPixels: 1,
      jointRounded: true,
      capRounded: true,
      getColor: [138, 160, 173],
    });
  }

  function carLayer(side, cars) {
    return new deck.SolidPolygonLayer({
      id: "cars-" + side,
      data: cars,
      extruded: true,
      getElevation: 1.6,
      getPolygon: (c) => R3.carFootprint(c.x, c.y, c.a, c.len, c.wid),
      getFillColor: (c, info) => CAR_COLORS[info.index % CAR_COLORS.length],
    });
  }

  function signalLayer(side, roadnet, tl) {
    const bars = [];
    for (const road of roadnet.roads) {
      const st = tl[road.id];
      if (!st) continue;
      const bs = R3.laneBars(road.points, road.nLanes, st, {});
      for (const b of bs) bars.push(b);
    }
    return new deck.SolidPolygonLayer({
      id: "signals-" + side,
      data: bars,
      extruded: true,
      getElevation: 2.5,
      getPolygon: (b) => b.polygon,
      getFillColor: (b) => (b.status === "g" ? [46, 204, 64] : [255, 65, 54]),
    });
  }

  // ---------- rendering ----------
  function render(side) {
    if (!S.roadnet) return;
    const step = S.steps[side][S.T];
    const layers = [roadLayer(S.roadnet)];
    if (step) {
      layers.push(carLayer(side, step.cars));
      layers.push(signalLayer(side, S.roadnet, step.tl));
    }
    decks[side].setProps({ layers });
  }
  function renderBoth() {
    render("left");
    render("right");
    $("clock").textContent = "t = " + S.T * DT + "s";
    $("scrub").value = String(S.T);
  }

  function renderScoreboard() {
    if (!S.comparison) return;
    const sb = RAB.scoreboard(S.comparison,
      CTRL_TO_ROW[S.ctrls.left], CTRL_TO_ROW[S.ctrls.right]);
    const cell = (e, name) => e
      ? '<div class="score"><b>' + name + "</b>" +
        "<span>" + e.vehH.toFixed(1) + " xe·giờ chờ (cả kịch bản)</span>" +
        "<span>" + (e.pctVsFixed >= 0 ? "▼ giảm " : "▲ tăng ") +
        Math.abs(e.pctVsFixed).toFixed(1) + "% so với Cố định</span></div>"
      : '<div class="score">—</div>';
    $("scoreboard").innerHTML =
      cell(sb.left, ctrlLabel(S.ctrls.left)) + cell(sb.right, ctrlLabel(S.ctrls.right));
  }

  // ---------- camera ----------
  function applyViewState(vs) {
    viewState = vs;
    window.__viewState = vs; // test hook
    decks.left.setProps({ viewState: vs });
    decks.right.setProps({ viewState: vs });
  }
  function refit() {
    const el = $("deck-left");
    fitState = R3.fitView(S.roadnet.bounds, el.clientWidth, el.clientHeight);
    applyViewState(Object.assign({}, fitState));
  }
  function makeDeck(el) {
    return new deck.Deck({
      parent: el,
      views: new deck.OrbitView({ orbitAxis: "Z" }),
      controller: true,
      viewState: { target: [0, 0, 0], zoom: 0, rotationX: 45, rotationOrbit: 0 },
      onViewStateChange: (e) => applyViewState(e.viewState),
      layers: [],
    });
  }

  // ---------- playback ----------
  function setPlaying(on) {
    S.playing = on;
    $("play").textContent = on ? "❚❚ Dừng" : "▶︎ Chạy";
    if (S.timer) { clearInterval(S.timer); S.timer = null; }
    if (on) {
      S.timer = setInterval(() => {
        const n = S.steps.left.length || 1;
        S.T = (S.T + 1) % n;
        renderBoth();
      }, parseInt($("speed").value, 10));
    }
  }

  // ---------- data loading (monotonic generation guards stale responses) ----------
  function loadAll(resetCamera) {
    const gen = ++S.gen;
    const sc = S.scenario;
    return Promise.all([
      fetchText(ROADNET(sc)),
      fetchText(REPLAY(sc, S.ctrls.left)),
      fetchText(REPLAY(sc, S.ctrls.right)),
      fetchText(COMPARISON(sc)),
    ]).then(([rnTxt, leftTxt, rightTxt, cmpTxt]) => {
      if (gen !== S.gen) return; // a newer request superseded this one
      S.roadnet = RAB.parseRoadnet(JSON.parse(rnTxt));
      S.steps.left = RAB.parseReplay(leftTxt);
      S.steps.right = RAB.parseReplay(rightTxt);
      S.comparison = JSON.parse(cmpTxt);
      const n = Math.min(S.steps.left.length, S.steps.right.length);
      $("scrub").max = String(Math.max(0, n - 1));
      if (S.T >= n) S.T = 0;
      if (resetCamera || !viewState) refit();
      renderBoth();
      renderScoreboard();
    }).catch((err) => {
      if (gen !== S.gen) return;
      const el = document.createElement("p");
      el.className = "err";
      el.textContent = "Lỗi tải dữ liệu: " + err.message;
      document.body.appendChild(el);
    });
  }

  // ---------- wiring ----------
  function fillSelect(el, pairs, value) {
    el.innerHTML = "";
    for (const [k, label] of pairs) {
      const o = document.createElement("option");
      o.value = k;
      o.textContent = label;
      el.appendChild(o);
    }
    el.value = value;
  }

  function init() {
    decks.left = makeDeck($("deck-left"));
    decks.right = makeDeck($("deck-right"));
    fillSelect($("scenario"), SCENARIOS, S.scenario);
    fillSelect($("ctrl-left"), CTRLS, S.ctrls.left);
    fillSelect($("ctrl-right"), CTRLS, S.ctrls.right);
    $("scenario").addEventListener("change", (e) => {
      S.scenario = e.target.value;
      loadAll(true); // new bounds (networks differ) -> refit camera
    });
    $("ctrl-left").addEventListener("change", (e) => {
      S.ctrls.left = e.target.value;
      $("left-title").textContent = ctrlLabel(S.ctrls.left);
      loadAll(false);
    });
    $("ctrl-right").addEventListener("change", (e) => {
      S.ctrls.right = e.target.value;
      $("right-title").textContent = ctrlLabel(S.ctrls.right);
      loadAll(false);
    });
    $("play").addEventListener("click", () => setPlaying(!S.playing));
    $("speed").addEventListener("change", () => { if (S.playing) setPlaying(true); });
    $("scrub").addEventListener("input", (e) => {
      S.T = parseInt(e.target.value, 10) || 0;
      renderBoth();
    });
    $("reset-cam").addEventListener("click", () => {
      if (fitState) applyViewState(Object.assign({}, fitState));
    });
    window.__replay3d = { state: S, applyViewState }; // test hook
    window.__decksReady = loadAll(true);
  }

  init();
})();
