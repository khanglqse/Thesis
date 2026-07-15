// Preset launcher + HUD for the RL traffic-signal demo.
// Architecture B: wraps the vendored CityFlow viewer without editing script.js.
// It fetches a (scenario, controller) roadnet+replay over HTTP and feeds them into
// the existing file inputs via the DataTransfer API, then clicks Start -- so the
// whole render path is reused unchanged. Removes the manual file-picker (the #1
// live-demo hazard) and adds an always-on, projector-legible HUD.
(function () {
  "use strict";

  // scenario key -> {label, roadnet replay-json}. Replays live at
  // results/<area>/demo/replay_<controller>_demo.txt (served by serve_replay.py).
  var SCENARIOS = {
    danang_peak:  { label: "Đà Nẵng giờ cao điểm (mix thực ~70% xe máy)",
                    roadnet: "/data/danang/replay_roadnet_danang_peak.json" },
    haichau_rush: { label: "Hải Châu — cao điểm thực tế (~50k xe · ~2.9k đồng thời)",
                    roadnet: "/data/danang/replay_roadnet_haichau_rush.json" },
    haichau:      { label: "Hải Châu — quá tải (stress test, ~1.2M xe)",
                    roadnet: "/data/danang/replay_roadnet_haichau.json" },
    full:         { label: "Toàn mạng (105 nút)",
                    roadnet: "/data/danang/replay_roadnet_full.json" }
  };
  var CONTROLLERS = {
    dqn:          "RL (DQN)",
    max_pressure: "Max-Pressure",
    fixed_time:   "Cố định (Fixed-Time)",
    random:       "Ngẫu nhiên"
  };

  function replayUrl(area, ctrl) {
    return "/results/" + area + "/demo/replay_" + ctrl + "_demo.txt";
  }

  // ---- HUD -------------------------------------------------------------
  var hud;
  function buildHUD() {
    var el = document.createElement("div");
    el.id = "demo-hud";
    el.innerHTML =
      '<div class="dh-scen"></div>' +
      '<div class="dh-ctrl"></div>' +
      '<div class="dh-stats"><span class="dh-step">step 0</span>' +
      '<span class="dh-veh">0 xe</span></div>' +
      '<div class="dh-score"></div>';
    document.getElementById("simulator-canvas").appendChild(el);
    return {
      root: el,
      scen: el.querySelector(".dh-scen"),
      ctrl: el.querySelector(".dh-ctrl"),
      step: el.querySelector(".dh-step"),
      veh: el.querySelector(".dh-veh"),
      score: el.querySelector(".dh-score"),
      set: function (scenLabel, ctrlKey) {
        this.scen.textContent = scenLabel;
        this.ctrl.textContent = CONTROLLERS[ctrlKey] || ctrlKey;
        this.ctrl.className = "dh-ctrl " + (ctrlKey === "dqn" ? "is-rl" : "is-base");
        this.score.textContent = "";
      }
    };
  }

  // Cumulative waiting time (vehicle-hours) from a per-decision queue trace,
  // matching eval/compare.py::cumulative_wait_hours (sum(queue * 10s) / 3600).
  function cumWaitHours(series) {
    var acc = 0;
    for (var i = 0; i < series.length; i++) acc += series[i] * 10 / 3600.0;
    return acc;
  }
  var CTRL_TO_ROW = { dqn: "DQN", fixed_time: "FixedTime",
                      max_pressure: "MaxPressure", random: "Random" };

  // Full-episode result scoreboard for the loaded (scenario, controller), from
  // results/<area>/comparison.json — the same run the replay was recorded from.
  function loadScoreboard(area, ctrl) {
    fetchText("/results/" + area + "/comparison.json").then(function (txt) {
      var table = JSON.parse(txt).table || [];
      var byName = {};
      table.forEach(function (r) { byName[r.controller] = r; });
      var fixed = byName["FixedTime"];
      var cur = byName[CTRL_TO_ROW[ctrl]];
      if (!cur || !cur.queue_series) { hud.score.textContent = ""; return; }
      var wh = cumWaitHours(cur.queue_series);
      var txt2 = "Cả episode: " + wh.toFixed(0) + " veh-h chờ";
      if (fixed && fixed.queue_series && CTRL_TO_ROW[ctrl] !== "FixedTime") {
        var fw = cumWaitHours(fixed.queue_series);
        var pct = fw ? (100 * (fw - wh) / fw) : 0;
        txt2 += "  ·  " + (pct >= 0 ? "▼ " : "▲ ") + Math.abs(pct).toFixed(1) +
                "% vs Fixed-Time";
      }
      hud.score.textContent = txt2;
    }).catch(function () { hud.score.textContent = ""; });
  }

  // Poll the viewer's own counters so the HUD stays in sync without touching script.js.
  function pollHUD() {
    var step = document.getElementById("current-step-num");
    var veh = document.getElementById("car-num");
    if (step && hud) hud.step.textContent = "step " + step.textContent;
    if (veh && hud) hud.veh.textContent = veh.textContent + " xe";
    requestAnimationFrame(pollHUD);
  }

  // ---- preset load -----------------------------------------------------
  function setFileInput(input, name, text, type) {
    var dt = new DataTransfer();
    dt.items.add(new File([text], name, { type: type }));
    input.files = dt.files;
  }

  function fetchText(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " " + url);
      return r.text();
    });
  }

  // ---- camera: whole-network vs zoom-in on a busy junction --------------
  // At whole-network scale hundreds of vehicles are 1px dots and the signals are
  // invisible; zooming the pixi-viewport onto the central cluster makes the moving
  // vehicles and the changing lights clearly visible -- the actual "wow".
  var zoomedIn = true;
  function nodePoints() {
    var sim = window.simulation;
    var pts = [];
    if (sim && sim.static && sim.static.nodes) {
      sim.static.nodes.forEach(function (n) {
        if (n.point && typeof n.point.x === "number") pts.push(n.point);
      });
    }
    return pts;
  }
  function carPositions() {
    var cc = window.carContainer, pts = [];
    if (cc && cc.children) {
      cc.children.forEach(function (s) {
        if (typeof s.x === "number") pts.push({ x: s.x, y: s.y });
      });
    }
    return pts;
  }
  function lightPositions() {
    var tl = window.trafficLightContainer, seen = {}, uniq = [];
    if (tl && tl.children) {
      tl.children.forEach(function (s) {
        if (typeof s.x !== "number") return;
        var k = Math.round(s.x / 100) + "," + Math.round(s.y / 100); // dedupe to junctions
        if (!seen[k]) { seen[k] = 1; uniq.push({ x: s.x, y: s.y }); }
      });
    }
    return uniq;
  }
  // Busiest signalized junction = the traffic-light position with the most cars
  // within radius R. Centering here guarantees BOTH signals and queuing vehicles
  // are in frame (the densest car cell alone is often mid-road, no light in view).
  function busiestJunction(cars, R) {
    var lights = lightPositions();
    if (!lights.length || !cars.length) return null;
    var best = null, bestn = 0;
    lights.forEach(function (L) {
      var n = 0;
      for (var i = 0; i < cars.length; i++) {
        if (Math.abs(cars[i].x - L.x) < R && Math.abs(cars[i].y - L.y) < R) n++;
      }
      if (n > bestn) { bestn = n; best = L; }
    });
    return bestn > 0 ? best : null;
  }
  function _screenW(v) { return v.screenWidth || window.innerWidth || 1200; }
  function applyCamera() {
    var v = window.viewport, nodes = nodePoints();
    if (!v || !nodes.length) return;
    var xs = nodes.map(function (p) { return p.x; }), ys = nodes.map(function (p) { return p.y; });
    var minx = Math.min.apply(null, xs), maxx = Math.max.apply(null, xs);
    var miny = Math.min.apply(null, ys), maxy = Math.max.apply(null, ys);
    var worldW = (maxx - minx) || 1;
    if (zoomedIn) {
      // Center on the busiest signalized junction (signals + queuing vehicles both
      // in frame); fall back to the network centroid if none found.
      var cars = carPositions(), cx, cy;
      var jn = busiestJunction(cars, 220);
      if (jn) {
        cx = jn.x; cy = jn.y;
      } else {
        cx = (minx + maxx) / 2; cy = (miny + maxy) / 2;
      }
      var target = Math.max(350, worldW / 15);      // ~one junction + its queues; cap on small nets
      v.setZoom(_screenW(v) / target);
      v.moveCenter(cx, cy);
    } else {
      v.setZoom(_screenW(v) / (worldW * 1.1));
      v.moveCenter((minx + maxx) / 2, (miny + maxy) / 2);
    }
  }
  function waitReadyThenCamera(tries) {
    tries = tries || 0;
    var cc = window.carContainer;
    if (window.viewport && nodePoints().length && cc && cc.children && cc.children.length) {
      applyCamera(); return;
    }
    if (tries < 80) setTimeout(function () { waitReadyThenCamera(tries + 1); }, 250);
  }

  function loadPreset(area, ctrl) {
    var scen = SCENARIOS[area];
    var status = document.getElementById("demo-status");
    status.textContent = "Đang nạp " + scen.label + " · " + (CONTROLLERS[ctrl] || ctrl) + " …";
    hud.set(scen.label, ctrl);
    loadScoreboard(area, ctrl);
    Promise.all([fetchText(scen.roadnet), fetchText(replayUrl(area, ctrl))])
      .then(function (res) {
        setFileInput(document.getElementById("roadnet-file"), "roadnet.json", res[0], "application/json");
        setFileInput(document.getElementById("replay-file"), "replay.txt", res[1], "text/plain");
        document.getElementById("start-btn").click();
        status.textContent = "Đang phát: " + scen.label;
        zoomedIn = true;
        waitReadyThenCamera();
      })
      .catch(function (e) {
        status.textContent = "Lỗi nạp: " + e.message +
          " (đã tạo demo replay cho scenario này chưa?)";
        console.error(e);
      });
  }

  // ---- UI panel --------------------------------------------------------
  function buildPanel() {
    var panel = document.createElement("div");
    panel.id = "demo-launcher";
    var scenOpts = Object.keys(SCENARIOS).map(function (k) {
      return '<option value="' + k + '">' + SCENARIOS[k].label + "</option>";
    }).join("");
    var ctrlOpts = Object.keys(CONTROLLERS).map(function (k) {
      return '<option value="' + k + '">' + CONTROLLERS[k] + "</option>";
    }).join("");
    panel.innerHTML =
      '<h5 class="dl-title">▶ Demo điều khiển đèn bằng RL</h5>' +
      '<label class="dl-lab">Kịch bản</label>' +
      '<select id="dl-scen" class="form-control mb-2">' + scenOpts + "</select>" +
      '<label class="dl-lab">Bộ điều khiển</label>' +
      '<select id="dl-ctrl" class="form-control mb-2">' + ctrlOpts + "</select>" +
      '<button id="dl-play" class="btn btn-primary w-100">▶ Chạy</button>' +
      '<button id="dl-zoom" class="btn btn-outline-secondary w-100 mt-2">🗺 Xem toàn cảnh</button>' +
      '<div id="demo-status" class="dl-status"></div>';
    // Put the launcher above the manual file-upload box.
    var host = document.getElementById("file-upload");
    host.parentNode.insertBefore(panel, host);
    document.getElementById("dl-play").addEventListener("click", function () {
      loadPreset(document.getElementById("dl-scen").value,
                 document.getElementById("dl-ctrl").value);
    });
    document.getElementById("dl-zoom").addEventListener("click", function () {
      zoomedIn = !zoomedIn;
      this.textContent = zoomedIn ? "🗺 Xem toàn cảnh" : "🔍 Nhìn gần 1 nút";
      applyCamera();
    });
  }

  function init() {
    buildPanel();
    hud = buildHUD();
    requestAnimationFrame(pollHUD);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
