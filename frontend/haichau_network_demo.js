(function () {
  "use strict";
  const core = window.HaiChauNetworkDemo;
  const base = document.documentElement.dataset.bundle || ".";
  const element = id => document.getElementById(id);
  const state = {
    manifest: null, network: null, summary: null,
    fixed: null, learned: null, selected: null,
    playing: false, lastTick: null,
  };

  function pathFor(relative) { return base.replace(/\/$/, "") + "/" + relative; }
  async function sha256(buffer) {
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(digest))
      .map(value => value.toString(16).padStart(2, "0")).join("");
  }
  async function fetchJson(relative, verify) {
    const response = await fetch(pathFor(relative), { cache: "no-store" });
    if (!response.ok) throw new Error(`Missing bundle file: ${relative}`);
    const bytes = await response.arrayBuffer();
    if (verify) {
      const expected = state.manifest.files[relative];
      if (!expected || await sha256(bytes) !== expected)
        throw new Error(`Hash mismatch: ${relative}`);
    }
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  function formatTime(seconds) {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  }
  function formatNumber(value, digits) {
    return value == null ? "—" : Number(value).toLocaleString(undefined, {
      maximumFractionDigits: digits == null ? 1 : digits,
    });
  }
  function metricMarkup(metrics) {
    const values = [
      [formatNumber(metrics.queue_integral_vehicle_seconds), "queue veh-s"],
      [formatNumber(metrics.completion_rate == null ? null : metrics.completion_rate * 100, 1) + (metrics.completion_rate == null ? "" : "%"), "completion"],
      [formatNumber(metrics.arrived, 0), "arrived"],
      [formatNumber(metrics.running, 0), "active"],
    ];
    return values.map(([value, label]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
  }
  function draw(canvas, replay, seconds) {
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    const transform = core.networkTransform(state.network.nodes, canvas.width, canvas.height, 34);
    const nodes = new Map(state.network.nodes.map(node => [node.id, node]));
    context.strokeStyle = "#496872";
    context.lineWidth = 1.2;
    for (const link of state.network.links || []) {
      const source = nodes.get(link.source), target = nodes.get(link.target);
      if (!source || !target) continue;
      context.beginPath();
      context.moveTo(transform.x(source.x), transform.y(source.y));
      context.lineTo(transform.x(target.x), transform.y(target.y));
      context.stroke();
    }
    const frame = replay.frames[core.frameIndexAt(replay.frames, seconds)];
    for (const vehicle of frame.vehicles || []) {
      context.fillStyle = "rgba(237,244,241,.42)";
      context.fillRect(transform.x(vehicle.x) - 1, transform.y(vehicle.y) - 1, 2, 2);
    }
    for (const node of state.network.nodes) {
      const reading = frame.nodes[node.id];
      const radius = 4 + Math.min(7, Math.sqrt(Number(reading.queue) || 0));
      const x = transform.x(node.x), y = transform.y(node.y);
      context.beginPath(); context.arc(x, y, radius, 0, Math.PI * 2);
      context.fillStyle = core.queueColor(reading.queue, state.manifest.queue_color_max || 50);
      context.fill();
      if (state.selected === node.id) {
        context.beginPath(); context.arc(x, y, radius + 4, 0, Math.PI * 2);
        context.strokeStyle = "#edf4f1"; context.lineWidth = 2; context.stroke();
      }
    }
    return frame;
  }
  function nodeState(replay, seconds, nodeId) {
    const frame = replay.frames[core.frameIndexAt(replay.frames, seconds)];
    return frame.nodes[nodeId];
  }
  function renderDetail(seconds) {
    if (!state.selected) return;
    const node = state.network.nodes.find(value => value.id === state.selected);
    const fixed = nodeState(state.fixed, seconds, node.id);
    const learned = nodeState(state.learned, seconds, node.id);
    const neighbors = (node.neighbors || []).map(id => {
      const left = nodeState(state.fixed, seconds, id);
      const right = nodeState(state.learned, seconds, id);
      return `<li><span>${id}</span><strong>${formatNumber(left.queue, 0)} / ${formatNumber(right.queue, 0)} veh</strong></li>`;
    }).join("") || "<li><span>No signal neighbors recorded</span></li>";
    element("selectionHint").textContent = "Fixed / DDQN at the synchronized time";
    element("nodeDetail").innerHTML = `
      <div class="node-heading"><strong>${node.id}</strong><span>${node.name || "controlled signal"}</span></div>
      <div class="node-pair">
        <div class="node-reading"><span>Fixed queue · phase</span><strong>${formatNumber(fixed.queue, 0)} · ${fixed.phase}</strong></div>
        <div class="node-reading"><span>DDQN queue · phase</span><strong>${formatNumber(learned.queue, 0)} · ${learned.phase}</strong></div>
      </div>
      <p class="context">Neighbor queues · fixed / DDQN</p><ul class="neighbors">${neighbors}</ul>`;
  }
  function render() {
    if (!state.fixed || !state.learned) return;
    const seconds = Number(element("seek").value);
    draw(element("fixedCanvas"), state.fixed, seconds);
    draw(element("learnedCanvas"), state.learned, seconds);
    element("fixedMetrics").innerHTML = metricMarkup(state.fixed.metrics);
    element("learnedMetrics").innerHTML = metricMarkup(state.learned.metrics);
    element("clock").textContent = formatTime(seconds);
    renderDetail(seconds);
  }
  function renderAggregate(regime) {
    const document = state.summary.summary || state.summary;
    const result = document.neighbor_phase_ddqn && document.neighbor_phase_ddqn[regime];
    const effect = result && result.queue_difference_vs_tuned_fixed;
    const target = element("aggregateEffect");
    if (!effect) {
      target.textContent = "No aggregate result";
      target.className = "bad";
      element("aggregateInterval").textContent = "The frozen summary has no matched effect for this regime.";
      return;
    }
    const relative = effect.relative_change_percent;
    target.textContent = `${relative > 0 ? "+" : ""}${formatNumber(relative, 1)}% vs tuned fixed`;
    target.className = relative <= 0 ? "good" : "bad";
    element("aggregateInterval").textContent = `95% paired CI: ${formatNumber(effect.bootstrap_ci95[0])} to ${formatNumber(effect.bootstrap_ci95[1])} vehicle-seconds · n=${effect.n_independent}`;
  }
  async function loadScenario(regime) {
    state.playing = false;
    element("play").textContent = "Play";
    element("status").textContent = "Verifying matched replay…";
    const pair = core.pairedReplays(state.manifest.replays.filter(entry => entry.regime === regime));
    [state.fixed, state.learned] = await Promise.all([
      fetchJson(pair.fixed.path, true), fetchJson(pair.learned.path, true),
    ]);
    const maximum = Math.min(
      state.fixed.frames[state.fixed.frames.length - 1].t,
      state.learned.frames[state.learned.frames.length - 1].t,
    );
    element("seek").max = maximum;
    element("seek").value = 0;
    state.selected = state.network.nodes[0].id;
    element("status").textContent = "Verified bundle loaded";
    renderAggregate(regime);
    render();
  }
  function selectFromCanvas(canvas, event) {
    const rect = canvas.getBoundingClientRect();
    const transform = core.networkTransform(state.network.nodes, canvas.width, canvas.height, 34);
    const mapped = state.network.nodes.map(node => ({
      id: node.id, x: transform.x(node.x), y: transform.y(node.y),
    }));
    const x = (event.clientX - rect.left) * canvas.width / rect.width;
    const y = (event.clientY - rect.top) * canvas.height / rect.height;
    const selected = core.nearestNode(mapped, x, y, 18);
    if (selected) { state.selected = selected.id; render(); }
  }
  function tick(timestamp) {
    if (!state.playing) return;
    if (state.lastTick == null) state.lastTick = timestamp;
    const elapsed = (timestamp - state.lastTick) / 1000 * Number(element("speed").value);
    if (elapsed >= 1) {
      state.lastTick = timestamp;
      element("seek").value = Math.min(Number(element("seek").max), Number(element("seek").value) + elapsed);
      if (Number(element("seek").value) >= Number(element("seek").max)) {
        state.playing = false; element("play").textContent = "Play";
      }
      render();
    }
    if (state.playing) requestAnimationFrame(tick);
  }
  async function start() {
    state.manifest = await fetchJson("manifest.json", false);
    if (state.manifest.controlled_signals !== 53 || state.manifest.demand_label !== element("provenance").textContent)
      throw new Error("Bundle scope or synthetic-demand label is invalid");
    [state.network, state.summary] = await Promise.all([
      fetchJson(state.manifest.network_path, true),
      fetchJson(state.manifest.aggregate_path, true),
    ]);
    if (state.network.controlled_signals !== 53)
      throw new Error("Network must contain exactly 53 controlled signals");
    core.validateNetwork(state.network.nodes);
    const regimes = [...new Set(state.manifest.replays.map(entry => entry.regime))];
    element("scenario").innerHTML = regimes.map(regime => `<option value="${regime}">${regime.replace(/_/g, " ")}</option>`).join("");
    await loadScenario(regimes[0]);
  }

  element("scenario").addEventListener("change", event => loadScenario(event.target.value).catch(fail));
  element("seek").addEventListener("input", render);
  element("play").addEventListener("click", () => {
    state.playing = !state.playing;
    element("play").textContent = state.playing ? "Pause" : "Play";
    state.lastTick = null;
    if (state.playing) requestAnimationFrame(tick);
  });
  element("reset").addEventListener("click", () => { element("seek").value = 0; render(); });
  for (const id of ["fixedCanvas", "learnedCanvas"])
    element(id).addEventListener("click", event => selectFromCanvas(element(id), event));
  function fail(error) {
    state.playing = false;
    element("status").textContent = error.message;
    element("status").className = "bad";
    console.error(error);
  }
  start().catch(fail);
})();
