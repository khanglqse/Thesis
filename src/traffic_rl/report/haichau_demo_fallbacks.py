"""Fail-closed provenance checks for Hai Chau v2 demo fallback media."""

import hashlib
import json
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign
from traffic_rl.eval.network_statistics import aggregate_campaign, evaluate_acceptance
from traffic_rl.report.media_validation import probe_pdf, probe_png, probe_video


FINAL_RELATIVE = Path("results/haichau_network_v2/final")
DEMAND_LABEL = "synthetic network demand constrained by Da Nang evidence"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path, label):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))


def _inside(root, relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s path is missing" % label)
    path = (Path(root) / relative).resolve()
    try:
        path.relative_to(Path(root).resolve())
    except ValueError:
        raise ValueError("%s path leaves the project root" % label)
    if not path.is_file():
        raise ValueError("%s is missing" % label)
    return path


def _canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _release_pdf(root, evidence):
    release = root / "paper/generated/haichau_network/thesis-release.json"
    pdf = root / "paper/thesis_danang.pdf"
    if not release.is_file() or not pdf.is_file():
        raise ValueError("hash-bound final thesis PDF is missing")
    record = _json(release, "thesis release")
    summary_hash = _canonical_hash(evidence["summary"])
    if record.get("summary_sha256") != summary_hash \
            or record.get("pdf_sha256") != _sha256(pdf):
        raise ValueError("final thesis PDF release hashes are stale")
    probe_pdf(pdf)
    return pdf


def _primary_controller(evidence):
    controller = evidence.get("protocol", {}).get(
        "primary_learned_controller", "neighbor_phase_ddqn")
    if controller not in ("neighbor_phase_ddqn", "schedule_residual_ddqn"):
        raise ValueError("final campaign has unsupported learned controller")
    return controller


def _representative_pairs(evidence):
    """Choose a predeclared, outcome-independent pair from each final regime."""
    primary_controller = _primary_controller(evidence)
    by_regime = {}
    for run in evidence["campaign"]["runs"]:
        if run.get("controller_id") not in ("tuned_fixed", primary_controller):
            continue
        regime = run.get("regime")
        if regime not in ("normal", "am_peak", "pm_peak"):
            continue
        by_regime.setdefault(regime, {}).setdefault(
            run["controller_id"], []).append(run)
    learned_seeds = sorted(set(
        run.get("learning_seed") for run in evidence["campaign"]["runs"]
        if run.get("controller_id") == primary_controller
        and isinstance(run.get("learning_seed"), int)
        and not isinstance(run.get("learning_seed"), bool)))
    if not learned_seeds:
        raise ValueError("final campaign has no DDQN learning seed")
    first_learning_seed = learned_seeds[0]
    selected = []
    for regime in ("normal", "am_peak", "pm_peak"):
        pair = by_regime.get(regime, {})
        fixed = sorted(pair.get("tuned_fixed", []), key=lambda item: item["run_id"])
        learned = sorted(
            (run for run in pair.get(primary_controller, [])
             if run.get("learning_seed") == first_learning_seed),
            key=lambda item: item["run_id"])
        demand_by_case = {}
        for run in fixed + learned:
            demand = run.get("scheduled_vehicles")
            if isinstance(demand, bool) or not isinstance(demand, int) or demand <= 0:
                raise ValueError("representative run lacks positive scheduled demand")
            case_id = run.get("case_id")
            if case_id in demand_by_case and demand_by_case[case_id] != demand:
                raise ValueError("matched runs disagree on scheduled demand")
            demand_by_case[case_id] = demand
        common_cases = sorted(set(run.get("case_id") for run in fixed)
                              & set(run.get("case_id") for run in learned))
        if not common_cases:
            raise ValueError("final campaign lacks a matched fixed/DDQN replay pair: %s" % regime)
        median_demand = statistics.median(demand_by_case[case] for case in common_cases)
        chosen_case = min(
            common_cases,
            key=lambda case: (abs(demand_by_case[case] - median_demand), case))
        matches = [(left, right) for left in fixed for right in learned
                   if left.get("case_id") == chosen_case
                   and right.get("case_id") == chosen_case]
        if not matches:
            raise ValueError("final campaign lacks a matched fixed/DDQN replay pair: %s" % regime)
        selected.append(matches[0])
    return selected


def _queue_color_scale(frame_records):
    """Return one common queue scale for every displayed A/B panel."""
    maximum = 0.0
    for frame_index, fixed_replay, learned_replay in frame_records:
        for replay in (fixed_replay, learned_replay):
            nodes = replay["frames"][frame_index].get("nodes", {})
            if not nodes:
                raise ValueError("walkthrough replay frame has no node metrics")
            maximum = max(maximum, max(float(row.get("queue", 0))
                                       for row in nodes.values()))
    return max(1.0, maximum)


def _replay_path(evidence, run):
    path = evidence["campaign_dir"] / "runs" / run["run_id"] / "replay.json"
    if not path.is_file():
        raise ValueError("final replay is missing: %s" % run["run_id"])
    replay = _json(path, "final replay")
    frames = replay.get("frames", [])
    if not frames or not isinstance(frames[0].get("nodes"), dict):
        raise ValueError("final replay has no node frames: %s" % run["run_id"])
    return path, replay


def _render_network(network, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nodes = network.get("nodes", [])
    if network.get("controlled_signals") != 53 or len(nodes) != 53:
        raise ValueError("frozen viewer network must contain 53 signals")
    positions = dict((node["id"], (float(node["x"]), float(node["y"])))
                     for node in nodes)
    figure, axis = plt.subplots(figsize=(10, 7), dpi=160)
    for link in network.get("links", []):
        if link.get("source") in positions and link.get("target") in positions:
            start, end = positions[link["source"]], positions[link["target"]]
            axis.plot((start[0], end[0]), (start[1], end[1]),
                      color="#9aabb0", linewidth=.55, zorder=1)
    axis.scatter([positions[node["id"]][0] for node in nodes],
                 [positions[node["id"]][1] for node in nodes],
                 s=26, color="#197278", edgecolor="#12343b", linewidth=.35, zorder=2)
    axis.set_title("Hải Châu: frozen 53-signal network\nSynthetic demand constrained by Da Nang evidence")
    axis.set_aspect("equal", adjustable="datalim")
    axis.set_axis_off()
    figure.tight_layout()
    figure.savefig(str(output), dpi=160)
    plt.close(figure)


def _render_walkthrough(network, pairs, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nodes = network["nodes"]
    positions = dict((node["id"], (float(node["x"]), float(node["y"])))
                     for node in nodes)
    render_frames = []
    for regime, (fixed_run, fixed_replay), (learned_run, learned_replay) in pairs:
        count = min(len(fixed_replay["frames"]), len(learned_replay["frames"]))
        indexes = sorted(set((0, max(0, count // 2), max(0, count - 1))))
        render_frames.extend((regime, fixed_run, fixed_replay, learned_run,
                              learned_replay, index) for index in indexes)
    queue_vmax = _queue_color_scale(
        [(index, fixed_replay, learned_replay)
         for _, _, fixed_replay, _, learned_replay, index in render_frames])
    with tempfile.TemporaryDirectory(prefix="haichau-demo-frames-") as temporary:
        frame_dir = Path(temporary)
        image_index = 0
        for (regime, fixed_run, fixed_replay, learned_run, learned_replay,
             frame_index) in render_frames:
            figure, axes = plt.subplots(
                1, 2, figsize=(12, 5), dpi=130, constrained_layout=True)
            for axis, title, replay in (
                    (axes[0], "Tuned fixed", fixed_replay),
                    (axes[1], "Neighbor phase DDQN", learned_replay)):
                frame = replay["frames"][frame_index]
                for link in network.get("links", []):
                    if link.get("source") in positions and link.get("target") in positions:
                        start, end = positions[link["source"]], positions[link["target"]]
                        axis.plot((start[0], end[0]), (start[1], end[1]),
                                  color="#b7c4c7", linewidth=.45, zorder=1)
                queues = [float(frame["nodes"].get(node["id"], {}).get("queue", 0))
                          for node in nodes]
                points = axis.scatter(
                    [positions[node["id"]][0] for node in nodes],
                    [positions[node["id"]][1] for node in nodes], c=queues,
                    cmap="YlOrRd", vmin=0, vmax=queue_vmax, s=30,
                    edgecolor="#243238", linewidth=.25, zorder=2)
                axis.set_title("%s · %s · t=%ss" % (regime.replace("_", " "), title,
                                                     frame.get("t", 0)))
                axis.set_aspect("equal", adjustable="datalim")
                axis.set_axis_off()
            figure.colorbar(points, ax=axes.ravel().tolist(), label="queued vehicles")
            figure.suptitle("Hải Châu final, hash-bound matched replay", fontsize=14)
            figure.savefig(str(frame_dir / ("frame-%03d.png" % image_index)))
            plt.close(figure)
            image_index += 1
        if not image_index:
            raise ValueError("no final replay frames are available for fallback video")
        command = [
            "ffmpeg", "-nostdin", "-y", "-v", "error", "-framerate", "1",
            "-i", str(frame_dir / "frame-%03d.png"), "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
        ]
        try:
            subprocess.check_call(command)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError("unable to encode fallback walkthrough: %s" % exc)
    return {
        "queue_color_vmin": 0.0,
        "queue_color_vmax": queue_vmax,
        "frame_count": len(render_frames),
        "selection_rule": "median_scheduled_demand_then_case_id_first_learning_seed",
        "runs": [run["run_id"] for _, fixed, learned in pairs
                 for run in (fixed[0], learned[0])],
    }


def build_fallbacks(project_root, output_dir, campaign_dir=None):
    """Build all required media from frozen v2 evidence into an empty directory."""
    root = Path(project_root).resolve()
    evidence = validate_final_evidence(root, campaign_dir)
    pdf = _release_pdf(root, evidence)
    output = Path(output_dir)
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        raise ValueError("fallback output must remain inside the project root")
    if output.exists() and any(output.iterdir()):
        raise ValueError("refusing to overwrite non-empty fallback output directory")
    output.mkdir(parents=True, exist_ok=True)
    network = _json(evidence["viewer_path"], "frozen viewer network")
    png = output / "network-overview.png"
    _render_network(network, png)
    pairs = []
    source_replays = {}
    for fixed, learned in _representative_pairs(evidence):
        fixed_path, fixed_replay = _replay_path(evidence, fixed)
        learned_path, learned_replay = _replay_path(evidence, learned)
        source_replays[fixed["run_id"]] = _sha256(fixed_path)
        source_replays[learned["run_id"]] = _sha256(learned_path)
        pairs.append((fixed["regime"], (fixed, fixed_replay), (learned, learned_replay)))
    mp4 = output / "demo-walkthrough.mp4"
    walkthrough_render = _render_walkthrough(network, pairs, mp4)
    result_pdf = output / "result-summary.pdf"
    shutil.copyfile(str(pdf), str(result_pdf))
    fallbacks = {
        mp4.name: _sha256(mp4), result_pdf.name: _sha256(result_pdf),
        png.name: _sha256(png),
    }
    provenance = {
        "schema_version": 1,
        "evidence_namespace": "haichau_network_v2",
        "campaign_manifest_sha256": _sha256(evidence["campaign_dir"] / "campaign-manifest.json"),
        "frozen_protocol_sha256": _sha256(evidence["campaign_dir"] / "frozen-protocol.json"),
        "summary_sha256": _canonical_hash(evidence["summary"]),
        "viewer_network_sha256": _sha256(evidence["viewer_path"]),
        "thesis_pdf_sha256": _sha256(pdf),
        "source_replay_sha256": source_replays,
        "walkthrough_render": walkthrough_render,
        "fallbacks": fallbacks,
    }
    _write_json(output / "fallback-provenance.json", provenance)
    validate_fallbacks(root, output, campaign_dir)
    return provenance


def validate_fallbacks(project_root, fallback_dir, campaign_dir=None):
    """Validate decodability and final-evidence provenance of all fallbacks."""
    root = Path(project_root).resolve()
    evidence = validate_final_evidence(root, campaign_dir)
    pdf = _release_pdf(root, evidence)
    directory = Path(fallback_dir).resolve()
    provenance = _json(directory / "fallback-provenance.json", "fallback provenance")
    expected = {
        "evidence_namespace": "haichau_network_v2",
        "campaign_manifest_sha256": _sha256(evidence["campaign_dir"] / "campaign-manifest.json"),
        "frozen_protocol_sha256": _sha256(evidence["campaign_dir"] / "frozen-protocol.json"),
        "summary_sha256": _canonical_hash(evidence["summary"]),
        "viewer_network_sha256": _sha256(evidence["viewer_path"]),
        "thesis_pdf_sha256": _sha256(pdf),
    }
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError("fallback provenance does not match final Hai Chau evidence")
    expected_runs = [run["run_id"] for fixed, learned in _representative_pairs(evidence)
                     for run in (fixed, learned)]
    walkthrough = provenance.get("walkthrough_render")
    if not isinstance(walkthrough, dict) \
            or walkthrough.get("runs") != expected_runs:
        raise ValueError(
            "fallback provenance walkthrough run IDs differ from predeclared pairs")
    expected_replay_hashes = {}
    for run_id in expected_runs:
        run = next((item for item in evidence["campaign"]["runs"]
                    if item.get("run_id") == run_id), None)
        if run is None:
            raise ValueError("predeclared walkthrough run is absent from final campaign")
        replay_path, _ = _replay_path(evidence, run)
        expected_replay_hashes[run_id] = _sha256(replay_path)
    if provenance.get("source_replay_sha256") != expected_replay_hashes:
        raise ValueError("fallback source replay hash mismatch")
    probes = {}
    for name, probe in (("demo-walkthrough.mp4", probe_video),
                        ("result-summary.pdf", probe_pdf),
                        ("network-overview.png", probe_png)):
        path = directory / name
        if not path.is_file() or provenance.get("fallbacks", {}).get(name) != _sha256(path):
            raise ValueError("fallback media hash mismatch: %s" % name)
        probes[name] = probe(path)
    if _sha256(directory / "result-summary.pdf") != _sha256(pdf):
        raise ValueError("result-summary PDF is not the final hash-bound thesis PDF")
    result = dict(provenance)
    result["probes"] = probes
    return result


def validate_final_evidence(project_root, campaign_dir=None):
    """Refuse every evidence location except the frozen Hai Chau v2 campaign."""
    root = Path(project_root).resolve()
    expected = (root / FINAL_RELATIVE).resolve()
    candidate = Path(campaign_dir).resolve() if campaign_dir else expected
    if candidate != expected:
        raise ValueError(
            "demo fallback evidence must be results/haichau_network_v2/final")
    if not candidate.is_dir():
        raise ValueError("frozen Hai Chau v2 final evidence directory is missing")
    protocol = _json(candidate / "frozen-protocol.json", "frozen protocol")
    campaign = _json(candidate / "campaign-manifest.json", "campaign manifest")
    summary = _json(candidate / "summary.json", "campaign summary")
    if protocol.get("evidence_namespace") != "haichau_network_v2" \
            or campaign.get("evidence_namespace") != "haichau_network_v2":
        raise ValueError("final evidence must declare the haichau_network_v2 namespace")
    scope = summary.get("study_scope", {})
    if scope.get("controlled_signals") != 53 \
            or scope.get("demand_label") != DEMAND_LABEL:
        raise ValueError("final evidence must describe 53-signal synthetic Hai Chau demand")
    network_path = _inside(root, protocol.get("network_manifest_path"),
                           "frozen network manifest")
    if _sha256(network_path) != protocol.get("network_manifest_sha256"):
        raise ValueError("frozen network manifest hash mismatch")
    network = _json(network_path, "frozen network manifest")
    agents = network.get("agent_ids", [])
    if network.get("controlled_signals") != 53 or len(agents) != 53 \
            or len(set(agents)) != 53:
        raise ValueError("frozen network manifest must identify 53 unique signals")
    viewer_hash = protocol.get("viewer_network_sha256")
    viewer_records = [entry for entry in network.get("artifacts", {}).values()
                      if isinstance(entry, dict)
                      and entry.get("sha256") == viewer_hash]
    if len(viewer_records) != 1:
        raise ValueError("frozen protocol must bind exactly one viewer network artifact")
    viewer_path = _inside(root, viewer_records[0].get("path"), "viewer network")
    if _sha256(viewer_path) != viewer_hash:
        raise ValueError("viewer network hash mismatch")
    runs = campaign.get("runs", [])
    if not runs:
        raise ValueError("final campaign has no runs")
    for run in runs:
        source = str(run.get("source_run_dir", "")).replace("\\", "/").lower()
        if ("sumo" in source or ("results/haichau" in source
                                  and "results/haichau_network_v2" not in source)):
            raise ValueError("legacy SUMO/single-junction evidence is forbidden")
        if run.get("evidence_namespace") != "haichau_network_v2" \
                or run.get("controlled_signals") != 53:
            raise ValueError("final campaign run is not a 53-signal Hai Chau v2 run")
    try:
        verified = verify_campaign(candidate)
        rows = []
        for run in runs:
            metrics = _json(candidate / "runs" / run["run_id"] / "metrics.json",
                            "final run metrics")
            row = dict(run)
            row.update(metrics)
            rows.append(row)
        rules = protocol.get("acceptance_rules", {})
        aggregate = aggregate_campaign(
            rows,
            required_learning_seeds=rules.get("required_learning_seeds"),
            required_regimes=rules.get(
                "required_regimes", ("normal", "am_peak", "pm_peak")),
            minimum_learning_seeds=rules.get("minimum_learning_seeds", 5),
            minimum_demand_units=rules.get("minimum_demand_units", 1),
            normal_point_limit=rules.get("normal_point_limit", 0.0),
            normal_ci_margin_fraction=rules.get("normal_ci_margin_fraction", 0.05),
            peak_ci_upper_limit=rules.get("peak_ci_upper_limit", 0.0),
            completion_degradation_limit=rules.get(
                "completion_degradation_limit", 0.02),
            primary_learned_controller=protocol.get("primary_learned_controller"),
        )
        expected_summary = {
            "study_scope": {
                "controlled_signals": 53,
                "demand_label": DEMAND_LABEL,
                "evidence_namespace": "haichau_network_v2",
            },
            "summary": aggregate,
            "acceptance": evaluate_acceptance(aggregate),
        }
        if summary != expected_summary:
            raise ValueError(
                "final campaign summary does not exactly recompute from verified runs")
    except ValueError as exc:
        raise ValueError("final campaign verification failed: %s" % exc)
    return {
        "campaign_dir": candidate,
        "protocol": protocol,
        "campaign": campaign,
        "summary": summary,
        "network_path": network_path,
        "viewer_path": viewer_path,
        "summary_path": candidate / "summary.json",
        "verified_runs": verified["complete"],
    }
