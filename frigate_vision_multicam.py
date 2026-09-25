#!/usr/bin/env python3
"""Frigate Vision multi-camera GIF renderer.

Builds one animated GIF from the recordings of several Frigate review items
(one per camera the object moved through), cutting from one camera to the
next at the moment the next camera picks the object up.

It is called by the "FrigateVision - Multi-Camera Journeys" blueprint
through a Home Assistant shell_command, and only uses what already ships in
the Home Assistant container (python3 and ffmpeg). Put it in
/config/frigate_vision/ and add this to configuration.yaml:

    shell_command:
      frigate_vision_multicam: "python3 /config/frigate_vision/frigate_vision_multicam.py {{ args }}"

Commands (arguments are key=value pairs):

    render job=<id> url=<frigate url> review=<camera>@<start>@<end>[@<seen>...]
           [review=...]
           [size=640] [shape=auto|landscape|portrait|square]
           [background=blur|black] [fps=8] [speed=2] [max_length=20]
           [pre=1] [post=2] [labels=1] [retries=3] [keep_hours=48]
        Each <seen> is when the camera picked up an object again during
        its review (the start time of each of the review's detections).
        Starts rendering in the background (shell_command stops anything
        that runs longer than 60 seconds) and prints
        {"status": "started", "genai": "<camera>@<severity> ..."}, where
        "genai" lists the cameras and review severities Frigate writes GenAI
        summaries for (left out if Frigate's config can't be read).

    status job=<id>
        Prints {"status": "running" | "done" | "failed", "url": ..., "error": ...}

The GIF is written to <config>/www/frigate_vision/<job>.gif, which Home
Assistant serves as /local/frigate_vision/<job>.gif.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPT = Path(__file__).resolve()
CONFIG_DIR = SCRIPT.parent.parent
JOBS_DIR = SCRIPT.parent / "jobs"
OUT_DIR = CONFIG_DIR / "www" / "frigate_vision"
URL_PREFIX = "/local/frigate_vision"

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
JOB_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

DEFAULTS = {
    "size": 640,
    "fps": 8,
    "speed": 2.0,
    "max_length": 20.0,
    "pre": 1.0,
    "post": 2.0,
    "labels": 1,
    "retries": 3,
    "keep_hours": 48,
}

# Pieces of the same camera less than this far apart come from one download
MERGE_GAP = 30.0
# Recordings downloaded at the same time
PARALLEL_DOWNLOADS = 3


def fail_usage(message):
    print(json.dumps({"status": "failed", "error": message}))
    sys.exit(0)


def parse_args(argv):
    opts = {"review": []}
    for arg in argv:
        key, sep, value = arg.partition("=")
        if not sep:
            fail_usage(f"expected key=value, got {arg!r}")
        if key == "review":
            opts["review"].append(value)
        else:
            opts[key] = value
    return opts


def job_paths(job):
    if not JOB_RE.match(job or ""):
        fail_usage("invalid job id")
    return JOBS_DIR / f"{job}.json", JOBS_DIR / f"{job}.status", JOBS_DIR / f"{job}.log"


def write_status(path, **status):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(status))
    tmp.replace(path)


# ── Timeline ────────────────────────────────────────────────────────────────


def last_seen(window, t):
    """When the window's camera last picked the object up, as of time t."""
    return max((s for s in window["seen"] if s <= t), default=window["seen"][0])


def build_timeline(reviews, pre, post):
    """Turn review items into a list of (camera, start, end) pieces.

    Each review covers [start, end + post]. A review that starts while no
    other review is showing also gets `pre` seconds of lead-in. At any moment
    the camera that most recently picked the object up is shown, so the GIF
    hard-cuts to the next camera as soon as it sees the object, and falls
    back to a camera that still sees it if the newer one loses it first.
    A camera that picks the object up again partway through its review
    (a new detection) counts as the newest from then on, so walking back to
    it cuts back straight away. Stretches where no camera saw anything are
    skipped.
    """
    reviews = sorted(reviews, key=lambda r: r["start"])
    windows = []
    for r in reviews:
        covered = any(
            o is not r and o["start"] < r["start"] <= o["end"] + post for o in reviews
        )
        windows.append(
            {
                "camera": r["camera"],
                "seen": [r["start"]]
                + sorted(t for t in r.get("seen", []) if r["start"] < t < r["end"]),
                "start": r["start"] if covered else r["start"] - pre,
                "end": r["end"] + post,
            }
        )

    bounds = sorted({w["start"] for w in windows} | {w["end"] for w in windows}
                    | {t for w in windows for t in w["seen"]})
    pieces = []
    for a, b in zip(bounds, bounds[1:]):
        mid = (a + b) / 2
        active = [w for w in windows if w["start"] <= mid < w["end"]]
        if not active:
            continue
        camera = max(active, key=lambda w: last_seen(w, mid))["camera"]
        if pieces and pieces[-1]["camera"] == camera and abs(pieces[-1]["end"] - a) < 1e-6:
            pieces[-1]["end"] = b
        else:
            pieces.append({"camera": camera, "start": a, "end": b})
    return [p for p in pieces if p["end"] - p["start"] >= 0.25]


# ── Recordings ──────────────────────────────────────────────────────────────


def media_info(path):
    """(duration in seconds or None, width, height) of a video file.

    The size is read from ffmpeg's stream info, swapped for a camera whose
    stream is flagged as rotated 90 degrees, so width/height are what is
    actually shown."""
    try:
        err = subprocess.run(
            [FFMPEG, "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0",
             "-c", "copy", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        ).stderr
    except subprocess.SubprocessError:
        return None, 0, 0

    width = height = 0
    size = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
    if size:
        width, height = int(size.group(1)), int(size.group(2))
        rotation = re.search(r"rotation of (-?[\d.]+) degrees", err)
        if rotation and round(abs(float(rotation.group(1)))) % 180 == 90:
            width, height = height, width

    duration = None
    if shutil.which("ffprobe"):
        try:
            duration = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, timeout=60,
            ).stdout.strip())
        except (ValueError, subprocess.SubprocessError):
            pass
    if duration is None:
        # Fall back to the last timestamp ffmpeg read
        times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if times:
            h, m, sec = times[-1]
            duration = int(h) * 3600 + int(m) * 60 + float(sec)
    return duration, width, height


def plan_downloads(pieces):
    """Group the timeline's pieces into the clips to download.

    A camera's pieces less than MERGE_GAP apart share one clip, so a journey
    that goes back and forth between two cameras downloads one clip per
    camera instead of one per cut."""
    clips = []
    for piece in pieces:
        clip = next((c for c in reversed(clips) if c["camera"] == piece["camera"]), None)
        if clip and piece["start"] - clip["end"] <= MERGE_GAP:
            clip["end"] = max(clip["end"], piece["end"])
            clip["pieces"].append(piece)
        else:
            clips.append({"camera": piece["camera"], "start": piece["start"],
                          "end": piece["end"], "pieces": [piece]})
    return clips


def download_clip(base_url, clip, dest, retries, log):
    """Download a clip's recording and return media_info() for it, or None.
    Frigate only has a recording once its segment is finished, so a clip that
    comes back missing or short is fetched again a few times."""
    url = (f"{base_url}/api/{clip['camera']}/start/{clip['start']:.3f}"
           f"/end/{clip['end']:.3f}/clip.mp4")
    wanted = clip["end"] - clip["start"]
    info = (None, 0, 0)
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(10)
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
        except urllib.error.HTTPError as err:
            log(f"{clip['camera']}: download failed ({err}), attempt {attempt + 1}")
            continue
        except (urllib.error.URLError, OSError) as err:
            # Frigate can't be reached at all, so retrying won't help
            log(f"{clip['camera']}: download failed ({err}), not retrying")
            break
        info = media_info(dest)
        log(f"{clip['camera']}: got {info[0]}s of {wanted:.1f}s at "
            f"{info[1]}x{info[2]}, attempt {attempt + 1}")
        if info[0] is None or info[0] >= wanted - 1.5:
            return info
    return info if dest.exists() and dest.stat().st_size > 0 else None


# ── Rendering ───────────────────────────────────────────────────────────────


def find_font():
    for pattern in ("/usr/share/fonts/**/*.ttf", "/usr/share/fonts/**/*.otf",
                    "/usr/local/share/fonts/**/*.ttf"):
        fonts = sorted(glob.glob(pattern, recursive=True))
        if fonts:
            preferred = [f for f in fonts if re.search(r"(?i)dejavusans\.|sans", f)]
            return (preferred or fonts)[0]
    return None


SHAPES = {"landscape": 16 / 9, "portrait": 9 / 16, "square": 1.0}


def canvas_size(inputs, size, shape):
    """Frame size for the GIF, with `size` as its long edge.

    "auto" matches the cameras: if they are all landscape (or all portrait)
    the GIF takes the shape of the camera shown longest; if the journey mixes
    both, the GIF is square so neither is squeezed into a thin strip."""
    if shape in SHAPES:
        aspect = SHAPES[shape]
    else:
        sized = [i for i in inputs if i["width"] and i["height"]]
        if not sized:
            aspect = SHAPES["landscape"]
        else:
            wide = {i["width"] >= i["height"] for i in sized}
            if len(wide) > 1:
                aspect = 1.0
            else:
                longest = max(sized, key=lambda i: i["length"])
                aspect = longest["width"] / longest["height"]
    if aspect >= 1:
        w, h = size, size / aspect
    else:
        w, h = size * aspect, size
    return int(round(w / 2)) * 2, int(round(h / 2)) * 2


def render_gif(inputs, opts, out_path, with_labels, log):
    w, h = canvas_size(inputs, int(opts["size"]), opts["shape"])
    fps = int(opts["fps"])
    speed = float(opts["speed"])
    blur = opts["background"] == "blur"
    font = find_font() if with_labels else None
    log(f"frame {w}x{h}, {'blurred' if blur else 'black'} background, labels={with_labels}")

    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    chains = []
    for i, item in enumerate(inputs):
        cmd += ["-ss", f"{item['offset']:.3f}", "-t", f"{item['length']:.3f}",
                "-i", str(item["path"])]
        base = f"[{i}:v]setpts=(PTS-STARTPTS)/{speed:.4f},fps={fps}"
        fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1"
        if blur:
            # The clip, fitted to the frame, over a blurred and darkened copy
            # of itself that fills the frame (like phones show vertical video)
            chain = (
                f"{base},split[f{i}][b{i}];"
                f"[b{i}]scale={w // 4}:{h // 4}:force_original_aspect_ratio=increase,"
                f"crop={w // 4}:{h // 4},boxblur=6:2,eq=brightness=-0.15,"
                f"scale={w}:{h},setsar=1[bg{i}];"
                f"[f{i}]{fit}[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2"
            )
        else:
            chain = f"{base},{fit},pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
        if with_labels:
            text = item["camera"].replace("-", " ").replace("_", " ")
            size = max(12, min(w, h) // 16)
            chain += (
                f",drawtext=text='{text}':x={size // 2}:y={size // 2}"
                f":fontsize={size}:fontcolor=white:box=1:boxcolor=black@0.5"
                f":boxborderw={max(2, size // 4)}"
            )
            if font:
                chain += f":fontfile='{font}'"
        chains.append(chain + f"[v{i}]")

    concat = "".join(f"[v{i}]" for i in range(len(inputs)))
    graph = ";".join(chains) + (
        f";{concat}concat=n={len(inputs)}:v=1:a=0,split[a][b];"
        "[a]palettegen=max_colors=192:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
    )
    cmd += ["-filter_complex", graph, "-loop", "0", str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        log(f"ffmpeg failed (labels={with_labels}): {result.stderr.strip()[-800:]}")
        return False
    return True


def cleanup(keep_hours):
    cutoff = time.time() - keep_hours * 3600
    for folder, patterns in ((OUT_DIR, ("*.gif",)), (JOBS_DIR, ("*.json", "*.status", "*.log"))):
        for pattern in patterns:
            for f in folder.glob(pattern):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                except OSError:
                    pass


def worker(job):
    spec_path, status_path, log_path = job_paths(job)
    opts = json.loads(spec_path.read_text())

    log_lock = threading.Lock()

    def log(message):
        with log_lock, open(log_path, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {message}\n")

    try:
        os.nice(10)
    except OSError:
        pass

    try:
        cleanup(float(opts["keep_hours"]))
        pieces = build_timeline(opts["reviews"], float(opts["pre"]), float(opts["post"]))
        log(f"timeline: {json.dumps(pieces)}")
        if not pieces:
            raise RuntimeError("nothing to render")

        clips = plan_downloads(pieces)
        with tempfile.TemporaryDirectory(prefix="frigate_vision_") as tmp:
            for i, clip in enumerate(clips):
                clip["path"] = Path(tmp) / f"clip{i}.mp4"
            with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as pool:
                infos = list(pool.map(
                    lambda c: download_clip(opts["url"], c, c["path"], int(opts["retries"]), log),
                    clips))
            for clip, info in zip(clips, infos):
                clip["info"] = info

            inputs = []
            for piece in pieces:
                clip = next(c for c in clips if any(piece is p for p in c["pieces"]))
                if clip["info"] is None:
                    continue
                duration, width, height = clip["info"]
                wanted = clip["end"] - clip["start"]
                # Frigate starts a clip on the keyframe before the requested
                # time, so skip any extra lead-in at the front
                lead = max(0.0, duration - wanted) if duration else 0.0
                offset = lead + piece["start"] - clip["start"]
                length = piece["end"] - piece["start"]
                if duration:
                    # A clip that came back short is missing its end
                    length = min(length, duration - offset)
                if length < 0.25:
                    continue
                inputs.append({"path": clip["path"], "camera": piece["camera"],
                               "offset": offset, "length": length,
                               "width": width, "height": height})
            if not inputs:
                raise RuntimeError("no recordings could be downloaded")

            total = sum(i["length"] for i in inputs)
            opts["speed"] = max(float(opts["speed"]), total / max(float(opts["max_length"]), 1))
            log(f"rendering {len(inputs)} piece(s) from {len(clips)} clip(s), "
                f"{total:.1f}s at {opts['speed']:.2f}x")

            OUT_DIR.mkdir(parents=True, exist_ok=True)
            tmp_gif = Path(tmp) / "out.gif"
            ok = int(opts["labels"]) and render_gif(inputs, opts, tmp_gif, True, log)
            if not ok:
                ok = render_gif(inputs, opts, tmp_gif, False, log)
            if not ok:
                raise RuntimeError("ffmpeg could not render the GIF (see log)")
            log(f"GIF: {tmp_gif.stat().st_size / 1048576:.1f} MB")
            final = OUT_DIR / f"{job}.gif"
            shutil.move(str(tmp_gif), final)
            final.chmod(0o644)

        log("done")
        write_status(status_path, status="done", url=f"{URL_PREFIX}/{job}.gif")
    except Exception as err:  # noqa: BLE001 - report every failure to the blueprint
        log(f"failed: {err}")
        write_status(status_path, status="failed", error=str(err))


# ── Commands ────────────────────────────────────────────────────────────────


def genai_reviews(url):
    """The cameras and review severities Frigate writes GenAI summaries for,
    as "<camera>@alert <camera>@detection ...", or None if Frigate's config
    can't be read. Frigate 0.17+ sets this per camera in review -> genai:
    off unless enabled, and then for alerts but not detections by default."""
    try:
        with urllib.request.urlopen(f"{url}/api/config", timeout=10) as resp:
            config = json.load(resp)
        cameras = config.get("cameras") or {}
        found = []
        for name, camera in cameras.items():
            genai = ((camera or {}).get("review") or {}).get("genai") or {}
            if not NAME_RE.match(name) or not genai.get("enabled"):
                continue
            if genai.get("alerts", True):
                found.append(f"{name}@alert")
            if genai.get("detections", False):
                found.append(f"{name}@detection")
        return " ".join(found)
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return None



def cmd_render(opts):
    job = opts.get("job", "")
    spec_path, status_path, log_path = job_paths(job)

    url = opts.get("url", "").strip().rstrip("/")
    if not re.match(r"^https?://[^\s'\"]+$", url):
        fail_usage("invalid Frigate url")

    reviews = []
    for value in opts["review"]:
        parts = value.split("@")
        if len(parts) < 3 or not NAME_RE.match(parts[0]):
            fail_usage(f"invalid review {value!r}")
        try:
            start, end = float(parts[1]), float(parts[2])
            seen = [float(t) for t in parts[3:]]
        except ValueError:
            fail_usage(f"invalid review {value!r}")
        if end < start:
            end = start
        reviews.append({"camera": parts[0], "start": start, "end": end, "seen": seen})
    if not reviews:
        fail_usage("no reviews given")

    # Check Frigate answers before starting, so a wrong URL fails straight
    # away with a clear error instead of every download hanging until the
    # blueprint gives up
    try:
        with urllib.request.urlopen(f"{url}/api/version", timeout=10):
            pass
    except (urllib.error.URLError, OSError, ValueError) as err:
        fail_usage(f"can't reach Frigate at {url} ({getattr(err, 'reason', err)})")

    spec = {"url": url, "reviews": reviews}
    for key, default in DEFAULTS.items():
        try:
            spec[key] = type(default)(float(opts.get(key, default)))
        except ValueError:
            fail_usage(f"invalid {key}")
    spec["size"] = max(120, min(spec["size"], 1920))
    spec["shape"] = opts.get("shape", "auto")
    if spec["shape"] not in ("auto", *SHAPES):
        fail_usage("invalid shape")
    spec["background"] = opts.get("background", "blur")
    if spec["background"] not in ("blur", "black"):
        fail_usage("invalid background")

    genai = genai_reviews(url)

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec))
    write_status(status_path, status="running")
    with open(log_path, "a") as log, open(os.devnull, "rb") as devnull:
        # Detached, with no pipes back to Home Assistant, so the
        # shell_command returns straight away
        subprocess.Popen(
            [sys.executable, str(SCRIPT), "worker", job],
            stdin=devnull, stdout=log, stderr=log, start_new_session=True,
        )
    started = {"status": "started"}
    if genai is not None:
        started["genai"] = genai
    print(json.dumps(started))


def cmd_status(opts):
    _, status_path, _ = job_paths(opts.get("job", ""))
    try:
        print(status_path.read_text())
    except OSError:
        print(json.dumps({"status": "failed", "error": "unknown job"}))


FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        fail_usage("usage: render|status key=value ...")
    command = sys.argv[1]
    if command == "worker" and len(sys.argv) == 3:
        worker(sys.argv[2])
    elif command == "render":
        cmd_render(parse_args(sys.argv[2:]))
    elif command == "status":
        cmd_status(parse_args(sys.argv[2:]))
    else:
        fail_usage(f"unknown command {command!r}")
