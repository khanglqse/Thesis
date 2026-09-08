"""Thesis artifacts and claim checks for the 53-node Hai Chau study."""

import hashlib
import json
import re
from pathlib import Path


_REGIME_LABELS = {
    "normal": "Normal",
    "am_peak": "AM peak",
    "pm_peak": "PM peak",
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
    return {"network_results": "\n".join(lines) + "\n"}


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
    return [queue_path, completion_path]


def write_artifacts(summary, output_dir, command):
    _scope(summary)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_sha256 = _summary_hash(summary)
    table_path = output_dir / "haichau_network_results.tex"
    table_path.write_text(build_tables(summary)["network_results"])
    _write_sidecar(table_path, summary_sha256, command)
    figure_paths = _write_figures(
        summary, output_dir, summary_sha256, command)
    manifest = {
        "summary_sha256": summary_sha256,
        "generation_command": command,
        "artifacts": [table_path.name] + [path.name for path in figure_paths],
    }
    (output_dir / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
