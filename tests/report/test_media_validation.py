import subprocess

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from traffic_rl.report.media_validation import probe_pdf, probe_png, probe_video


def _figure(path):
    fig, ax = plt.subplots(figsize=(1, 1))
    ax.plot([0, 1], [0, 1])
    fig.savefig(path)
    plt.close(fig)


def test_media_probes_open_rendered_nonempty_files(tmp_path):
    pdf = tmp_path / "result.pdf"
    png = tmp_path / "overview.png"
    mp4 = tmp_path / "walkthrough.mp4"
    _figure(pdf)
    _figure(png)
    subprocess.check_call([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=32x24:d=0.2",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4),
    ])

    assert probe_pdf(pdf)["pages"] >= 1
    assert probe_png(png)["width"] > 0
    assert probe_video(mp4)["duration_seconds"] > 0


@pytest.mark.parametrize("kind, payload", [
    ("pdf", b"%PDF-1.4\n%%EOF\n"),
    ("png", b"\x89PNG\r\n\x1a\nfixture"),
    ("video", b"\x00\x00\x00\x18ftypisom"),
])
def test_magic_signature_placeholders_are_rejected(tmp_path, kind, payload):
    path = tmp_path / ("payload." + {"pdf": "pdf", "png": "png", "video": "mp4"}[kind])
    path.write_bytes(payload)
    probe = {"pdf": probe_pdf, "png": probe_png, "video": probe_video}[kind]
    with pytest.raises(ValueError, match="usable|decode|parse|render|video"):
        probe(path)
