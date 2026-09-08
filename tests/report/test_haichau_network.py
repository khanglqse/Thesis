import json

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
    written = write_artifacts(_summary(), tmp_path, command="build-test")
    assert (tmp_path / "haichau_network_results.tex").is_file()
    assert (tmp_path / "paired-queue-difference.png").is_file()
    sidecar = json.loads(
        (tmp_path / "paired-queue-difference.png.provenance.json").read_text())
    assert sidecar["summary_sha256"] == written["summary_sha256"]
    assert sidecar["generation_command"] == "build-test"
