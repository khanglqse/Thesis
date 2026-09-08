"""Decoder-backed validation for release PDFs, PNGs and video fallbacks."""

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path


def _run(argv):
    try:
        completed = subprocess.run(
            [str(value) for value in argv], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
    except OSError as exc:
        raise ValueError("required media decoder is unavailable: %s" % exc)
    if completed.returncode:
        raise ValueError("media decode/parse failed: %s" % completed.stderr.strip())
    return completed.stdout


def _ffprobe(path):
    output = _run((
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", Path(path),
    ))
    try:
        return json.loads(output)
    except ValueError:
        raise ValueError("media decoder returned invalid JSON")


def _decode_video_stream(path, first_frame_only=False):
    argv = [
        "ffmpeg", "-nostdin", "-v", "error", "-xerror",
        "-i", Path(path), "-map", "0:v:0",
    ]
    if first_frame_only:
        argv.extend(("-frames:v", "1"))
    argv.extend(("-f", "null", "-"))
    _run(argv)


def _positive(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def probe_png(path):
    payload = _ffprobe(path)
    streams = [stream for stream in payload.get("streams", [])
               if stream.get("codec_type") == "video"]
    if len(streams) != 1 or streams[0].get("codec_name") != "png" \
            or not _positive(streams[0].get("width")) \
            or not _positive(streams[0].get("height")):
        raise ValueError("PNG is not a usable decoded image")
    _decode_video_stream(path, first_frame_only=True)
    return {
        "width": int(streams[0]["width"]),
        "height": int(streams[0]["height"]),
        "codec": "png",
    }


def probe_video(path):
    payload = _ffprobe(path)
    streams = [stream for stream in payload.get("streams", [])
               if stream.get("codec_type") == "video"]
    duration = payload.get("format", {}).get("duration")
    if not duration and streams:
        duration = streams[0].get("duration")
    if not streams or not _positive(streams[0].get("width")) \
            or not _positive(streams[0].get("height")) \
            or not _positive(duration):
        raise ValueError("fallback video requires a decodable video stream and duration")
    _decode_video_stream(path)
    return {
        "width": int(streams[0]["width"]),
        "height": int(streams[0]["height"]),
        "duration_seconds": float(duration),
        "codec": streams[0].get("codec_name"),
    }


def probe_pdf(path):
    output = _run(("pdfinfo", Path(path)))
    match = re.search(r"^Pages:\s+(\d+)\s*$", output, flags=re.MULTILINE)
    pages = int(match.group(1)) if match else 0
    if pages <= 0:
        raise ValueError("PDF parser found no usable pages")
    with tempfile.TemporaryDirectory(prefix="haichau-pdf-probe-") as temporary:
        target = Path(temporary) / "page"
        _run(("pdftoppm", "-f", "1", "-singlefile", "-r", "24", "-png",
              Path(path), target))
        rendered = target.with_suffix(".png")
        if not rendered.is_file():
            raise ValueError("PDF first page did not render")
        dimensions = probe_png(rendered)
    return {"pages": pages, "rendered_first_page": dimensions}
