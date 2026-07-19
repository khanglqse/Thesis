(function () {
  "use strict";
  const RAB = window.ReplayAB, R3 = window.Replay3D;
  const DEFAULT_SCENARIO = "haichau_rush";
  const ROADNET = (sc) => `/data/danang/replay_roadnet_${sc}.json`;

  const decks = {};
  let viewState = null, fitState = null;

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

  function applyViewState(vs) {
    viewState = vs;
    window.__viewState = vs; // test hook
    decks.left.setProps({ viewState: vs });
    decks.right.setProps({ viewState: vs });
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

  function showError(err) {
    const el = document.createElement("p");
    el.className = "err";
    el.textContent = "Lỗi tải dữ liệu: " + err.message;
    document.body.appendChild(el);
  }

  window.__decksReady = new Promise((resolve, reject) => {
    const holderL = document.getElementById("deck-left");
    const holderR = document.getElementById("deck-right");
    decks.left = makeDeck(holderL);
    decks.right = makeDeck(holderR);
    document.getElementById("reset-cam").addEventListener("click", () => {
      if (fitState) applyViewState(Object.assign({}, fitState));
    });
    fetch(ROADNET(DEFAULT_SCENARIO))
      .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then((data) => {
        const rn = RAB.parseRoadnet(data);
        fitState = R3.fitView(rn.bounds, holderL.clientWidth, holderL.clientHeight);
        applyViewState(Object.assign({}, fitState));
        decks.left.setProps({ layers: [roadLayer(rn)] });
        decks.right.setProps({ layers: [roadLayer(rn)] });
        resolve(true);
      })
      .catch((err) => { showError(err); reject(err); });
  });
})();
