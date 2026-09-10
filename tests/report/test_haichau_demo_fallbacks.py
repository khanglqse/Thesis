import hashlib
import json

import pytest


LABEL = "synthetic network demand constrained by Da Nang evidence"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _pdf(path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots()
    axis.text(.2, .5, "Final Hai Chau evidence")
    figure.savefig(path)
    plt.close(figure)


def _final_root(root, source_run_dir="results/haichau_network_v2/final/runs/a"):
    final = root / "results/haichau_network_v2/final"
    viewer = root / "release/viewer-network.json"
    _write(viewer, {
        "controlled_signals": 53,
        "nodes": [{"id": "N%02d" % i, "x": i, "y": i,
                   "neighbors": []} for i in range(53)],
        "links": [],
    })
    network = root / "release/network-manifest.json"
    _write(network, {
        "controlled_signals": 53,
        "agent_ids": ["N%02d" % i for i in range(53)],
        "artifacts": {"viewer_network": {
            "path": "release/viewer-network.json", "sha256": _sha(viewer),
        }},
    })
    summary = {
        "study_scope": {"controlled_signals": 53, "demand_label": LABEL},
        "summary": {}, "acceptance": {"accepted": False},
    }
    _write(final / "summary.json", summary)
    runs = []
    for regime in ("normal", "am_peak", "pm_peak"):
        for controller in ("tuned_fixed", "neighbor_phase_ddqn"):
            run_id = "%s-%s" % (regime, controller)
            run = {"run_id": run_id, "controlled_signals": 53,
                   "evidence_namespace": "haichau_network_v2",
                   "source_run_dir": source_run_dir,
                   "case_id": "test-" + regime, "regime": regime,
                   "controller_id": controller,
                   "scheduled_vehicles": 1000,
                   "learning_seed": (11 if controller == "neighbor_phase_ddqn"
                                     else None)}
            runs.append(run)
            _write(final / "runs" / run_id / "replay.json", {
                "sample_seconds": 5,
                "frames": [{"t": 0, "nodes": {
                    "N%02d" % i: {"queue": float(i % 5), "phase": i % 3}
                    for i in range(53)}, "vehicles": []},
                {"t": 5, "nodes": {
                    "N%02d" % i: {"queue": float((i + 1) % 5), "phase": i % 3}
                    for i in range(53)}, "vehicles": []}],
            })
    _write(final / "campaign-manifest.json", {
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    })
    _write(final / "frozen-protocol.json", {
        "evidence_namespace": "haichau_network_v2",
        "network_manifest_path": "release/network-manifest.json",
        "network_manifest_sha256": _sha(network),
        "viewer_network_sha256": _sha(viewer),
    })
    thesis = root / "paper/thesis_danang.pdf"
    _pdf(thesis)
    _write(root / "paper/generated/haichau_network/thesis-release.json", {
        "summary_sha256": hashlib.sha256(
            json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "pdf_sha256": _sha(thesis),
    })
    return final


def test_final_evidence_refuses_legacy_campaign_directory(tmp_path):
    from traffic_rl.report.haichau_demo_fallbacks import validate_final_evidence

    legacy = tmp_path / "results" / "haichau" / "final"
    legacy.mkdir(parents=True)
    with pytest.raises(ValueError, match="haichau_network_v2/final"):
        validate_final_evidence(tmp_path, legacy)


def test_final_evidence_refuses_a_legacy_sumo_run_even_under_v2_directory(tmp_path):
    from traffic_rl.report.haichau_demo_fallbacks import validate_final_evidence

    final = _final_root(tmp_path, "results/haichau_peak/sumo/run-1")
    with pytest.raises(ValueError, match="legacy.*SUMO"):
        validate_final_evidence(tmp_path, final)


def test_demo_server_refuses_a_legacy_bundle_path(tmp_path):
    from scripts.serve_haichau_demo import validate_demo_bundle

    with pytest.raises(ValueError, match="results/haichau_network_v2/demo"):
        validate_demo_bundle(tmp_path, tmp_path / "results/haichau/demo")


def test_representative_pairs_use_median_demand_and_first_learning_seed():
    from traffic_rl.report.haichau_demo_fallbacks import _representative_pairs

    runs = []
    for regime in ("normal", "am_peak", "pm_peak"):
        for case_id, demand in (("case-low", 100), ("case-mid", 200),
                                ("case-high", 900)):
            runs.append({"run_id": "%s-fixed" % case_id, "regime": regime,
                         "case_id": case_id, "controller_id": "tuned_fixed",
                         "scheduled_vehicles": demand, "learning_seed": None})
            for seed in (13, 11):
                runs.append({"run_id": "%s-ddqn-%d" % (case_id, seed),
                             "regime": regime, "case_id": case_id,
                             "controller_id": "neighbor_phase_ddqn",
                             "scheduled_vehicles": demand, "learning_seed": seed})

    selected = _representative_pairs({"campaign": {"runs": runs}})

    assert [(left["case_id"], right["learning_seed"])
            for left, right in selected] == [("case-mid", 11)] * 3


def test_shared_queue_color_scale_covers_both_controller_panels():
    from traffic_rl.report.haichau_demo_fallbacks import _queue_color_scale

    fixed = {"frames": [{"nodes": {"a": {"queue": 2}, "b": {"queue": 8}}}]}
    learned = {"frames": [{"nodes": {"a": {"queue": 50}, "b": {"queue": 1}}}]}

    assert _queue_color_scale([(0, fixed, learned)]) == 50.0


def test_representative_pairs_support_schedule_residual_controller():
    from traffic_rl.report.haichau_demo_fallbacks import _representative_pairs

    runs = []
    for regime in ("normal", "am_peak", "pm_peak"):
        for controller, seed in (("tuned_fixed", None),
                                 ("schedule_residual_ddqn", 12)):
            runs.append({"run_id": "%s-%s" % (regime, controller),
                         "regime": regime, "controller_id": controller,
                         "learning_seed": seed, "case_id": regime + "-case",
                         "scheduled_vehicles": 100})
    selected = _representative_pairs({
        "protocol": {"primary_learned_controller": "schedule_residual_ddqn"},
        "campaign": {"runs": runs}})

    assert [right["controller_id"] for left, right in selected] == [
        "schedule_residual_ddqn"] * 3
