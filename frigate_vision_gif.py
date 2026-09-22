#!/usr/bin/env python3
"""
frigate_vision_gif.py - multi-camera GIF builder for FrigateVision Multi-Cam.

Takes the Frigate tracked objects (events) that made up one "session" across
several cameras and stitches Frigate's own preview GIFs into a single GIF that
cuts between cameras as the subject moves. At any moment the camera that most
recently picked the subject up is shown; if it loses them while another camera
still has them, the GIF cuts back to that camera. Stretches where no camera
sees anything are skipped.

Called from Home Assistant via shell_command (see README). Uses only the
Python standard library and ffmpeg, both of which ship with Home Assistant.

Modes
  check  Ask Frigate for the current start/end time of each track. Used by the
         blueprint to notice tracks that ended while it was not listening.
  build  Build the GIF, save it under --out-dir and print its URL.

Output is always a single JSON object on stdout.

Tracks are passed as  camera|event_id|start|end;camera|event_id|start|end
(end may be empty for a track that has not ended yet).
"""

import argparse
import concurrent.futures
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

CAMERA_RE = re.compile(r"^[A-Za-z0-9_-]+$")
EVENT_ID_RE = re.compile(r"^[0-9]+(\.[0-9]+)?-[A-Za-z0-9]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

FRIGATE_GIF_SPEED = 0.12  # Frigate plays preview GIFs at 0.12x real time
MAX_ATTACHMENT_BYTES = 9_500_000  # mobile notification images max out at 10MB


def parse_tracks(spec):
    tracks = []
    for part in filter(None, (p.strip() for p in spec.split(";"))):
        fields = part.split("|")
        if len(fields) != 4:
            raise ValueError(f"bad track: {part!r}")
        camera, event_id, start, end = fields
        if not CAMERA_RE.match(camera) or not EVENT_ID_RE.match(event_id):
            raise ValueError(f"bad camera or event id: {part!r}")
        tracks.append(
            {
                "camera": camera,
                "id": event_id,
                "start": float(start) if start else None,
                "end": float(end) if end else None,
            }
        )
    return tracks


def http_get(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def refresh_tracks(frigate, tracks, timeout=10):
    """Replace blueprint-supplied times with Frigate's own, where available."""

    def fetch(track):
        try:
            event = json.loads(http_get(f"{frigate}/api/events/{track['id']}", timeout))
            return track["id"], event.get("start_time"), event.get("end_time"), True
        except (urllib.error.URLError, ValueError, OSError):
            return track["id"], None, None, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = {r[0]: r[1:] for r in pool.map(fetch, tracks)}

    for track in tracks:
        start, end, found = results[track["id"]]
        track["found"] = found
        if found:
            track["start"] = start if start is not None else track["start"]
            track["end"] = end
    return tracks


def build_timeline(tracks, now, min_piece=2.0, merge_gap=1.5, pre_pad=2.0,
                   post_pad=2.0, gap_pad=1.0, max_track=900.0):
    """
    Turn overlapping per-camera intervals into an ordered list of pieces
    [{camera, start, end}], showing the most recently started camera whenever
    several cameras overlap.
    """
    # 1. per-camera intervals, merging overlaps and tiny gaps
    per_camera = {}
    for t in tracks:
        if t["start"] is None:
            continue
        end = t["end"] if t["end"] is not None else now
        end = min(end, t["start"] + max_track)  # e.g. a person parked on the porch
        if end <= t["start"]:
            continue
        per_camera.setdefault(t["camera"], []).append([t["start"], end])

    intervals = []
    for camera, spans in per_camera.items():
        spans.sort()
        merged = [spans[0]]
        for s, e in spans[1:]:
            if s <= merged[-1][1] + merge_gap:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        intervals += [{"camera": camera, "start": s, "end": e} for s, e in merged]

    if not intervals:
        return []

    # 2. sweep the boundaries; the covering interval with the latest start wins
    points = sorted({iv["start"] for iv in intervals} | {iv["end"] for iv in intervals})
    pieces = []
    for a, b in zip(points, points[1:]):
        covering = [iv for iv in intervals if iv["start"] <= a and iv["end"] >= b]
        if not covering:
            continue
        camera = max(covering, key=lambda iv: iv["start"])["camera"]
        if pieces and pieces[-1]["camera"] == camera and pieces[-1]["end"] >= a - merge_gap:
            pieces[-1]["end"] = b
        else:
            pieces.append({"camera": camera, "start": a, "end": b})

    # 3. fold pieces too short to show into the piece before them (or, for a
    #    short first piece, the one after), then re-merge same-camera runs
    def touching(a, b):
        return b["start"] - a["end"] <= merge_gap

    folded = []
    for p in pieces:
        if folded and p["end"] - p["start"] < min_piece and touching(folded[-1], p):
            folded[-1]["end"] = p["end"]
        else:
            folded.append(dict(p))
    if len(folded) > 1 and folded[0]["end"] - folded[0]["start"] < min_piece \
            and touching(folded[0], folded[1]):
        folded[1]["start"] = folded.pop(0)["start"]
    for i in range(len(folded) - 1, 0, -1):
        a, b = folded[i - 1], folded[i]
        if a["camera"] == b["camera"] and b["start"] - a["end"] <= merge_gap:
            a["end"] = b["end"]
            del folded[i]
    pieces = folded

    # 4. padding: before the first piece, after the last, and around gaps
    pieces[0]["start"] -= pre_pad
    pieces[-1]["end"] = min(pieces[-1]["end"] + post_pad, now)
    for a, b in zip(pieces, pieces[1:]):
        gap = b["start"] - a["end"]
        if gap > 0:
            pad = min(gap_pad, gap / 2)
            a["end"] += pad
            b["start"] -= pad
    return pieces


def fetch_pieces(frigate, pieces, workdir, timeout):
    def fetch(item):
        index, piece = item
        url = (
            f"{frigate}/api/{piece['camera']}/start/{piece['start']:.3f}"
            f"/end/{piece['end']:.3f}/preview.gif"
        )
        path = os.path.join(workdir, f"piece_{index:03d}.gif")
        try:
            data = http_get(url, timeout)
        except (urllib.error.URLError, OSError):
            return None
        if not data.startswith(b"GIF"):
            return None
        with open(path, "wb") as fh:
            fh.write(data)
        return dict(piece, path=path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, enumerate(pieces)))
    return [r for r in results if r]


def render(ffmpeg, pieces, out_path, width, fps, speed):
    height = int(round(width * 9 / 16 / 2)) * 2
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for p in pieces:
        cmd += ["-i", p["path"]]

    chains = [
        f"[{i}:v]fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
        for i in range(len(pieces))
    ]

    joined = "".join(f"[v{i}]" for i in range(len(pieces)))
    graph = ";".join(chains)
    graph += f";{joined}concat=n={len(pieces)}:v=1:a=0"
    if speed < 1:
        graph += f",setpts={speed:.4f}*PTS,fps={fps}"
    graph += ",split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"

    cmd += ["-filter_complex", graph, "-loop", "0", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0:
        if os.path.exists(out_path):
            os.remove(out_path)
        raise RuntimeError(proc.stderr.strip()[-500:] or "ffmpeg failed")


def cleanup(out_dir, keep_days):
    if keep_days <= 0:
        return
    cutoff = time.time() - keep_days * 86400
    for path in glob.glob(os.path.join(out_dir, "*.gif")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def cmd_check(args):
    tracks = refresh_tracks(args.frigate, parse_tracks(args.tracks))
    return {
        "tracks": {
            t["id"]: {"start": t["start"], "end": t["end"]} for t in tracks if t["found"]
        }
    }


def cmd_build(args):
    if not NAME_RE.match(args.name):
        raise ValueError("bad --name")
    started = time.time()
    tracks = refresh_tracks(args.frigate, parse_tracks(args.tracks))
    pieces = build_timeline(tracks, now=time.time(), min_piece=args.min_piece)
    if not pieces:
        raise RuntimeError("no usable tracks")

    real_seconds = sum(p["end"] - p["start"] for p in pieces)
    gif_seconds = real_seconds * FRIGATE_GIF_SPEED
    speed = min(1.0, args.max_gif_seconds / gif_seconds) if gif_seconds else 1.0

    os.makedirs(args.out_dir, exist_ok=True)
    cleanup(args.out_dir, args.keep_days)
    out_path = os.path.join(args.out_dir, f"{args.name}.gif")

    with tempfile.TemporaryDirectory(prefix="frigate_vision_") as workdir:
        fetched = fetch_pieces(args.frigate, pieces, workdir, timeout=20)
        if not fetched:
            raise RuntimeError("Frigate returned no preview GIFs for these tracks")

        width = args.width
        for _ in range(3):
            render(args.ffmpeg, fetched, out_path, width, args.fps, speed)
            if os.path.getsize(out_path) <= MAX_ATTACHMENT_BYTES:
                break
            width = int(width * 0.75) // 2 * 2

    return {
        "url": f"{args.url_prefix.rstrip('/')}/{args.name}.gif",
        "file": out_path,
        "bytes": os.path.getsize(out_path),
        "cameras": [p["camera"] for p in fetched],
        "pieces": [
            {"camera": p["camera"], "start": round(p["start"], 2), "end": round(p["end"], 2)}
            for p in fetched
        ],
        "seconds": round(real_seconds, 1),
        "build_seconds": round(time.time() - started, 1),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mode", choices=["check", "build"], default="build")
    parser.add_argument("--frigate", required=True, help="Frigate API base URL, e.g. http://ccab4aaf-frigate:5000")
    parser.add_argument("--tracks", required=True)
    parser.add_argument("--name", default="session")
    parser.add_argument("--out-dir", default="/config/www/frigate_vision")
    parser.add_argument("--url-prefix", default="/local/frigate_vision")
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--max-gif-seconds", type=float, default=20)
    parser.add_argument("--min-piece", type=float, default=2.0)
    parser.add_argument("--keep-days", type=float, default=7)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    args.frigate = args.frigate.rstrip("/")

    try:
        result = cmd_check(args) if args.mode == "check" else cmd_build(args)
    except Exception as err:  # report every failure as JSON for the blueprint
        print(json.dumps({"error": str(err)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
