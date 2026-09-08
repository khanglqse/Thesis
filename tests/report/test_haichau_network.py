import json
import hashlib
from pathlib import Path

from traffic_rl.report.haichau_network import (
    build_tables,
    validate_claims,
    write_artifacts,
)


def _effect(mean, low, high, baseline=100.0):
    return {
        "mean": mean,
        "bootstrap_ci95": [low, high],
        "relative_change_percent": mean,
        "baseline_mean": baseline,
        "n_independent": 5,
        "independent_values": [mean] * 5,
    }


def _summary():
    return {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
        },
        "summary": {
            "tuned_fixed": {
                "normal": {
                    "queue": {"mean": 100.0},
                    "completion_rate": {"mean": 0.95},
                },
                "pm_peak": {
                    "queue": {"mean": 120.0},
                    "completion_rate": {"mean": 0.94},
                },
            },
            "neighbor_phase_ddqn": {
                "normal": {
                    "queue": {"mean": 99.0},
                    "completion_rate": {"mean": 0.95},
                    "queue_difference_vs_tuned_fixed": _effect(-1.0, -3.0, 1.0),
                },
                "pm_peak": {
                    "queue": {"mean": 100.0},
                    "completion_rate": {"mean": 0.93},
                    "queue_difference_vs_tuned_fixed": _effect(-20.0, -25.0, -15.0, 120.0),
                },
            },
            "max_pressure": {
                "normal": {
                    "queue": {"mean": 90.0},
                    "completion_rate": {"mean": 0.96},
                },
            },
            "hysteretic_mp": {
                "normal": {
                    "queue": {"mean": 91.0},
                    "completion_rate": {"mean": 0.96},
                },
            },
            "shared_ddqn_legacy": {
                "normal": {
                    "queue": {"mean": 93.0},
                    "completion_rate": {"mean": 0.95},
                },
            },
        },
        "acceptance": {
            "accepted": True,
            "normal_point_noninferiority": True,
            "normal_ci_noninferiority": True,
            "peak_improvement": True,
            "completion_preserved": True,
            "five_learning_seeds": True,
        },
    }


def test_network_table_labels_demand_synthetic():
    table = build_tables(_summary())["network_results"]
    assert "synthetic" in table.lower()
    assert "53" in table
    assert "PM peak" in table
    assert "n=5 independent training seeds" in table
    assert "five matched demand/simulator cases" in table
    assert "pointwise two-sided percentile bootstrap" in table
    assert "10,000 resamples" in table
    assert "lower queue is better" in table


def test_thesis_states_pointwise_network_ci_limitation():
    thesis = Path(__file__).resolve().parents[2] / "paper/thesis_danang.tex"
    text = thesis.read_text()
    assert "pointwise" in text
    assert "no multiplicity correction" in text
    assert "either-peak" in text
    assert "frozen matched demand/simulator cases" in text


def test_claim_validator_rejects_citywide_observed_claim():
    errors = validate_claims("Results cover 53 observed intersections.", _summary())
    assert errors
    assert "synthetic" in errors[0].lower()


def test_claim_validator_rejects_success_when_acceptance_failed():
    summary = _summary()
    summary["acceptance"]["accepted"] = False
    errors = validate_claims(
        "The network controller passes all acceptance gates.", summary)
    assert any("acceptance" in error.lower() for error in errors)


def test_artifacts_record_exact_summary_hash_and_command(tmp_path):
    thesis = tmp_path / "thesis.tex"
    thesis.write_text("thesis fixture")
    output = tmp_path / "generated"
    written = write_artifacts(
        _summary(), output, command="build-test", thesis_path=thesis)
    assert (output / "haichau_network_results.tex").is_file()
    assert (output / "haichau_controller_comparison.tex").is_file()
    assert (output / "paired-queue-difference.png").is_file()
    sidecar = json.loads(
        (output / "paired-queue-difference.png.provenance.json").read_text())
    assert sidecar["summary_sha256"] == written["summary_sha256"]
    assert sidecar["generation_command"] == "build-test"
    assert written["thesis_source_sha256"] == hashlib.sha256(
        thesis.read_bytes()).hexdigest()
    assert isinstance(written["artifacts"], dict)
    for name, expected in written["artifacts"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected


def test_controller_comparison_table_includes_every_required_controller():
    table = build_tables(_summary())["controller_comparison"]
    for name in (
            "Tuned fixed", "Max-Pressure", "Hysteretic Max-Pressure",
            "Shared DDQN legacy", "Neighbor phase DDQN"):
        assert name in table


def test_artifact_generation_removes_stale_output(tmp_path):
    thesis = tmp_path / "thesis.tex"
    thesis.write_text("thesis fixture")
    output = tmp_path / "generated"
    output.mkdir()
    (output / "stale-table.tex").write_text("unsupported old result")

    write_artifacts(_summary(), output, "build-test", thesis_path=thesis)

    assert not (output / "stale-table.tex").exists()
