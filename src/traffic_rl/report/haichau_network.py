"""Thesis artifacts and claim checks for the 53-node Hai Chau study."""

import hashlib
import json
import re
import shutil
from pathlib import Path


_REGIME_LABELS = {
    "normal": "Normal",
    "am_peak": "AM peak",
    "pm_peak": "PM peak",
}

_CONTROLLER_LABELS = {
    "tuned_fixed": "Tuned fixed",
    "max_pressure": "Max-Pressure",
    "hysteretic_mp": "Hysteretic Max-Pressure",
    "shared_ddqn_legacy": "Shared DDQN legacy",
    "neighbor_phase_ddqn": "Neighbor phase DDQN",
}


def _document(summary):
    return summary.get("summary", summary)


def _scope(summary):
    scope = summary.get("study_scope", {})
    if scope.get("controlled_signals") != 53:
        raise ValueError("summary must identify exactly 53 controlled signals")
    label = str(scope.get("demand_label", ""))
    if "synthetic" not in label.lower():
        raise ValueError("network demand must be explicitly labeled synthetic")
    return scope


def _format_number(value):
    return "--" if value is None else "%.2f" % float(value)


def build_tables(summary):
    scope = _scope(summary)
    document = _document(summary)
    candidate = document.get("neighbor_phase_ddqn", {})
    baseline = document.get("tuned_fixed", {})
    regimes = [name for name in ("normal", "am_peak", "pm_peak")
               if name in candidate and name in baseline]
    if not regimes:
        raise ValueError("summary has no matched network regimes")
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Matched 53-signal network results. Demand is %s.}" %
        scope["demand_label"].replace("_", r"\_"),
        r"\label{tab:haichau-network-results}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Regime & Fixed queue & DDQN queue & Difference (95\% CI) & Completion \\",
        r"\midrule",
    ]
    for regime in regimes:
        result = candidate[regime]
        effect = result.get("queue_difference_vs_tuned_fixed", {})
        ci = effect.get("bootstrap_ci95", [None, None])
        lines.append("%s & %s & %s & %s [%s, %s] & %.3f \\\\" % (
            _REGIME_LABELS[regime],
            _format_number(baseline[regime]["queue"]["mean"]),
            _format_number(result["queue"]["mean"]),
            _format_number(effect.get("mean")),
            _format_number(ci[0]), _format_number(ci[1]),
            float(result["completion_rate"]["mean"]),
        ))
    lines.extend((r"\bottomrule", r"\end{tabular}", r"\end{table}"))
    comparison = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Complete matched controller comparison on the 53-signal network.}",
        r"\label{tab:haichau-controller-comparison}",
        r"\begin{tabular}{llrr}", r"\toprule",
        r"Controller & Regime & Queue integral & Completion \\", r"\midrule",
    ]
    for controller_id in _CONTROLLER_LABELS:
        for regime in ("normal", "am_peak", "pm_peak"):
            result = document.get(controller_id, {}).get(regime)
            if not result:
                continue
            comparison.append("%s & %s & %s & %.3f \\\\" % (
                _CONTROLLER_LABELS[controller_id], _REGIME_LABELS[regime],
                _format_number(result["queue"]["mean"]),
                float(result["completion_rate"]["mean"]),
            ))
    comparison.extend((r"\bottomrule", r"\end{tabular}", r"\end{table}"))
    return {
        "network_results": "\n".join(lines) + "\n",
        "controller_comparison": "\n".join(comparison) + "\n",
    }


def validate_claims(tex, summary):
    _scope(summary)
    errors = []
    observed_patterns = (
        r"53\s+(?:directly\s+)?observed\s+(?:signal(?:ized)?\s+)?intersections?",
        r"observed\s+(?:citywide|district-wide|network(?:-wide)?)\s+demand",
        r"(?:citywide|district-wide|network(?:-wide)?)\s+observed\s+demand",
        r"(?:fully\s+)?calibrated\s+(?:Hải\s+Châu|Hai\s+Chau|53[- ](?:node|signal))",
    )
    for pattern in observed_patterns:
        if re.search(pattern, tex, flags=re.IGNORECASE):
            errors.append(
                "The 53-node evidence uses synthetic network demand; "
                "citywide observed/calibrated wording is unsupported.")
            break
    accepted = bool(summary.get("acceptance", {}).get("accepted"))
    if not accepted and re.search(
            r"(?:passes|passed)\s+(?:all\s+)?acceptance\s+gates|"
            r"accepted\s+(?:deployment\s+)?candidate", tex, re.IGNORECASE):
        errors.append(
            "The text claims acceptance although the frozen acceptance result failed.")
    return errors


def _summary_hash(summary):
    encoded = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_sidecar(path, summary_sha256, command):
    sidecar = Path(str(path) + ".provenance.json")
    sidecar.write_text(json.dumps({
        "artifact": path.name,
        "generation_command": command,
        "summary_sha256": summary_sha256,
    }, indent=2, sort_keys=True) + "\n")


def _write_figures(summary, output_dir, summary_sha256, command):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    document = _document(summary)
    candidate = document["neighbor_phase_ddqn"]
    baseline = document["tuned_fixed"]
    regimes = [name for name in ("normal", "am_peak", "pm_peak")
               if name in candidate and name in baseline]
    labels = [_REGIME_LABELS[name] for name in regimes]

    means, low_error, high_error = [], [], []
    for regime in regimes:
        effect = candidate[regime]["queue_difference_vs_tuned_fixed"]
        means.append(effect["mean"])
        low_error.append(effect["mean"] - effect["bootstrap_ci95"][0])
        high_error.append(effect["bootstrap_ci95"][1] - effect["mean"])
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    colors = ["#257a5a" if value <= 0 else "#b54335" for value in means]
    ax.bar(np.arange(len(regimes)), means, color=colors,
           yerr=np.asarray([low_error, high_error]), capsize=4)
    ax.axhline(0, color="#28323c", linewidth=1)
    ax.set_xticks(np.arange(len(regimes)), labels)
    ax.set_ylabel("DDQN - tuned fixed queue integral (vehicle-seconds)")
    ax.set_title("Matched differences; lower is better")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    queue_path = output_dir / "paired-queue-difference.png"
    fig.savefig(queue_path, dpi=180)
    fig.savefig(output_dir / "paired-queue-difference.pdf")
    plt.close(fig)

    x = np.arange(len(regimes))
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(x - 0.18, [baseline[name]["completion_rate"]["mean"] for name in regimes],
           width=0.36, label="Tuned fixed", color="#60768a")
    ax.bar(x + 0.18, [candidate[name]["completion_rate"]["mean"] for name in regimes],
           width=0.36, label="Neighbor phase DDQN", color="#d39031")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Completion rate")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    completion_path = output_dir / "completion-rate.png"
    fig.savefig(completion_path, dpi=180)
    fig.savefig(output_dir / "completion-rate.pdf")
    plt.close(fig)
    for path in (queue_path, output_dir / "paired-queue-difference.pdf",
                 completion_path, output_dir / "completion-rate.pdf"):
        _write_sidecar(path, summary_sha256, command)
    return [
        queue_path, output_dir / "paired-queue-difference.pdf",
        completion_path, output_dir / "completion-rate.pdf",
    ]


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_artifacts(summary, output_dir, command, thesis_path=None):
    _scope(summary)
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(str(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_sha256 = _summary_hash(summary)
    tables = build_tables(summary)
    for key, filename in (
            ("network_results", "haichau_network_results.tex"),
            ("controller_comparison", "haichau_controller_comparison.tex")):
        table_path = output_dir / filename
        table_path.write_text(tables[key])
        _write_sidecar(table_path, summary_sha256, command)
    _write_figures(
        summary, output_dir, summary_sha256, command)
    artifact_paths = sorted(
        path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "summary_sha256": summary_sha256,
        "generation_command": command,
        "thesis_source_sha256": (
            _sha256(thesis_path) if thesis_path is not None else None),
        "artifacts": dict((path.name, _sha256(path)) for path in artifact_paths),
    }
    (output_dir / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def write_release_manifest(summary, output_dir, thesis_path, pdf_path, command):
    """Bind the compiled PDF to the exact summary, source and generated set."""
    output_dir = Path(output_dir)
    artifact_manifest = output_dir / "artifact-manifest.json"
    thesis_path = Path(thesis_path)
    pdf_path = Path(pdf_path)
    if not all(path.is_file() for path in (
            artifact_manifest, thesis_path, pdf_path)):
        raise ValueError("artifact manifest, thesis source and PDF are required")
    if not pdf_path.read_bytes().startswith(b"%PDF-"):
        raise ValueError("compiled thesis is not a PDF payload")
    manifest = {
        "summary_sha256": _summary_hash(summary),
        "artifact_manifest_sha256": _sha256(artifact_manifest),
        "thesis_source_sha256": _sha256(thesis_path),
        "pdf_sha256": _sha256(pdf_path),
        "generation_command": command,
    }
    (output_dir / "thesis-release.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
