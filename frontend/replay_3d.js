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
  // Motorbikes keep the warm pastel spread; cars get a distinct cool palette so
  // the ~90/10 motorbike-to-car mix of this network is visible at a glance.
  const MOTO_COLORS = [[242, 191, 215], [219, 235, 183], [245, 221, 181],
                       [212, 181, 245], [240, 205, 170]];
  const CAR_COLORS = [[122, 178, 232], [232, 236, 242], [126, 199, 186],
                      [166, 176, 196]];
  const DT = 1; // seconds per replay frame (CityFlow logs one frame per 1s step)

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

  // Two shapes, split by the CityFlow template the replay recorded for each
  // vehicle: 5.0 m long -> car, otherwise motorbike (~90% here). Nothing is
  // scaled up — the meshes are the template size, so a 2 m motorbike is only
  // legible once the camera is close (see the "Điểm đông" button).
  // deck 9 wants the loaders.gl mesh shape; a plain {positions, normals, indices}
  // object throws inside getModel. The core stays dependency-free typed arrays.
  const toDeckMesh = (m) => ({
    attributes: {
      POSITION: { value: m.positions, size: 3 },
      NORMAL: { value: m.normals, size: 3 },
    },
    indices: { value: m.indices, size: 1 },
  });
  const MESHES = { motorbike: toDeckMesh(R3.vehicleMesh("motorbike")),
                   car: toDeckMesh(R3.vehicleMesh("car")) };
  const CAR_IS_CAR = (c) => c.len >= 3.5;

  function vehicleLayer(side, kind, cars, palette) {
    return new deck.SimpleMeshLayer({
      id: "veh-" + kind + "-" + side,
      data: cars,
      mesh: MESHES[kind],
      getPosition: (c) => [c.x, c.y, 0],
      // replay `a` is radians CCW with 0 = +x; deck takes [pitch, yaw, roll] in degrees
      getOrientation: (c) => [0, -c.a * 180 / Math.PI, 0],
      getColor: (c, info) => palette[info.index % palette.length],
      material: { ambient: 0.5, diffuse: 0.6, shininess: 24, specularColor: [60, 64, 70] },
    });
  }

  function vehicleLayers(side, cars) {
    const motos = [], cars4 = [];
    for (const c of cars) (CAR_IS_CAR(c) ? cars4 : motos).push(c);
    return [
      vehicleLayer(side, "motorbike", motos, MOTO_COLORS),
      vehicleLayer(side, "car", cars4, CAR_COLORS),
    ];
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
      for (const l of vehicleLayers(side, step.cars)) layers.push(l);
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
  // Whole-network fit renders a 2 m vehicle at ~0.1 px and a lane bar thinner
  // still, so at the default camera only the roads are visible. This drops the
  // camera onto the busiest cell of the replay at BUSY_SPAN metres across, where
  // vehicles and per-lane bars are actually readable.
  // 170 m across puts a 2 m motorbike at ~9 px, which is where the vehicle
  // meshes stop reading as specks; the steeper pitch keeps queues legible.
  const BUSY_SPAN = 170, BUSY_PITCH = 62;
  function zoomBusy() {
    if (!viewState || !S.roadnet) return;
    const step = S.steps.left[S.T] || S.steps.left[0];
    const sig = step ? RAB.signalizedInters(S.roadnet, step.tl) : [];
    const spot = RAB.busiestJunction(S.steps.left, sig.length ? sig : S.roadnet.inters,
                                     { radius: 120, every: 10 })
              || RAB.busiestSpot(S.steps.left, { cell: 400, every: 10 });
    if (!spot) return;
    const el = $("deck-left");
    const zoom = R3.zoomForSpan(el.clientWidth, BUSY_SPAN);
    applyViewState(Object.assign({}, viewState, {
      target: [spot.x, spot.y, 0],
      rotationX: BUSY_PITCH,
      zoom: zoom,
      maxZoom: Math.max(zoom + 1, viewState.maxZoom == null ? zoom + 1 : viewState.maxZoom),
    }));
  }

  // Without a light the mesh vehicles shade flat and read as the boxes they
  // replaced; one ambient + one directional light gives them visible facets.
  function makeLighting() {
    return new deck.LightingEffect({
      // keep the total modest: brighter than this and the pastel vehicle colours
      // wash out to white, losing the motorbike/car distinction
      ambient: new deck.AmbientLight({ color: [255, 255, 255], intensity: 0.9 }),
      sun: new deck.DirectionalLight({
        color: [255, 255, 255], intensity: 0.8, direction: [-0.6, -0.8, -1.0] }),
    });
  }

  function makeDeck(el) {
    return new deck.Deck({
      parent: el,
      views: new deck.OrbitView({ orbitAxis: "Z" }),
      controller: true,
      effects: [makeLighting()],
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
    $("zoom-busy").addEventListener("click", zoomBusy);
    $("reset-cam").addEventListener("click", () => {
      if (fitState) applyViewState(Object.assign({}, fitState));
    });
    window.__replay3d = { state: S, applyViewState, zoomBusy }; // test hook
    window.__decksReady = loadAll(true);
  }

  init();
})();
