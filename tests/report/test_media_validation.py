import struct
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


def test_png_probe_rejects_corrupt_idat_even_when_ffprobe_reads_dimensions(tmp_path):
    png = tmp_path / "corrupt.png"
    _figure(png)
    payload = bytearray(png.read_bytes())
    offset = 8
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = bytes(payload[offset + 4:offset + 8])
        if kind == b"IDAT":
            payload[offset + 8 + max(1, length // 2)] ^= 0xFF
            break
        offset += 12 + length
    else:
        pytest.fail("fixture PNG has no IDAT chunk")
    png.write_bytes(payload)
    assert subprocess.call([
        "ffprobe", "-v", "error", "-show_streams", str(png),
    ]) == 0

    with pytest.raises(ValueError, match="decode/parse"):
        probe_png(png)


def test_video_probe_rejects_truncated_faststart_payload(tmp_path):
    mp4 = tmp_path / "corrupt.mp4"
    subprocess.check_call([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=32x24:d=1", "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4),
    ])
    mp4.write_bytes(mp4.read_bytes()[:-128])
    assert subprocess.call([
        "ffprobe", "-v", "error", "-show_streams", str(mp4),
    ]) == 0

    with pytest.raises(ValueError, match="decode/parse"):
        probe_video(mp4)


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
