#!/bin/bash
# frigate_collage.sh
#
# Downloads a Frigate event clip, extracts 4 frames at 10/35/60/90% through
# the clip, stamps each with the camera name and timestamp, then assembles
# them into a 2×2 collage saved to /config/www/frigate/.
#
# Usage:
#   frigate_collage.sh "<clip_url>" "<event_id>" "<camera_name>"
#
# Output:
#   /config/www/frigate/frigate_event_<camera>_<event_id>.jpg
#
# Requirements:
#   - curl
#   - ffmpeg / ffprobe

set -e

CLIP_URL="$1"
EVENT_ID="$2"
CAMERA="$3"

WORK_DIR="/config/www/frigate"

mkdir -p "$WORK_DIR"

LOCAL_CLIP="$WORK_DIR/${EVENT_ID}.mp4"

FRAME1="$WORK_DIR/${EVENT_ID}_1.jpg"
FRAME2="$WORK_DIR/${EVENT_ID}_2.jpg"
FRAME3="$WORK_DIR/${EVENT_ID}_3.jpg"
FRAME4="$WORK_DIR/${EVENT_ID}_4.jpg"

LABELED1="$WORK_DIR/${EVENT_ID}_labeled_1.jpg"
LABELED2="$WORK_DIR/${EVENT_ID}_labeled_2.jpg"
LABELED3="$WORK_DIR/${EVENT_ID}_labeled_3.jpg"
LABELED4="$WORK_DIR/${EVENT_ID}_labeled_4.jpg"

COLLAGE="$WORK_DIR/frigate_event_${CAMERA}_${EVENT_ID}.jpg"

# ── Font discovery ─────────────────────────────────────────────────────────
# Alpine/HA OS ships no fonts by default. Search common paths and fall back
# to skipping labels entirely rather than crashing.
find_font() {
  for f in \
    /usr/share/fonts/dejavu/DejaVuSans-Bold.ttf \
    /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf \
    /usr/share/fonts/TTF/DejaVuSans-Bold.ttf \
    /usr/share/fonts/dejavu/DejaVuSans.ttf \
    /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf \
    /usr/share/fonts/TTF/DejaVuSans.ttf \
    /usr/share/fonts/liberation/LiberationSans-Bold.ttf \
    /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf \
    /usr/share/fonts/truetype/freefont/FreeSans.ttf \
    /usr/share/fonts/freefont/FreeSans.ttf; do
    [ -f "$f" ] && echo "$f" && return 0
  done
  # Last resort: find anything usable
  find /usr/share/fonts -name "*.ttf" 2>/dev/null | head -1
}

FONT=$(find_font)

if [ -z "$FONT" ]; then
  echo "WARNING: No font found — labels will be skipped."
  echo "Install dejavu-fonts (apk add ttf-dejavu) for camera/timestamp labels."
  SKIP_LABELS=1
else
  echo "Using font: $FONT"
  SKIP_LABELS=0
fi

echo "==== START ===="
echo "Downloading clip..."

curl -L "$CLIP_URL" -o "$LOCAL_CLIP"

echo "Downloaded:"
ls -lah "$LOCAL_CLIP"

test -f "$LOCAL_CLIP"

# ── Duration ───────────────────────────────────────────────────────────────
DURATION=$(ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  "$LOCAL_CLIP")

echo "Duration: $DURATION"

if [ -z "$DURATION" ]; then
  echo "ERROR: Could not determine clip duration"
  exit 1
fi

# ── Timestamps at 10 / 35 / 60 / 90 % ────────────────────────────────────
T1=$(awk "BEGIN {print $DURATION * 0.1}")
T2=$(awk "BEGIN {print $DURATION * 0.35}")
T3=$(awk "BEGIN {print $DURATION * 0.6}")
T4=$(awk "BEGIN {print $DURATION * 0.9}")

echo "Extracting frames at: $T1  $T2  $T3  $T4"

# -update 1 is required in ffmpeg 6+ when writing a single image to a
# non-patterned filename (e.g. foo.jpg instead of foo_%03d.jpg)
ffmpeg -y -ss "$T1" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME1"
ffmpeg -y -ss "$T2" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME2"
ffmpeg -y -ss "$T3" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME3"
ffmpeg -y -ss "$T4" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME4"

test -f "$FRAME1"
test -f "$FRAME2"
test -f "$FRAME3"
test -f "$FRAME4"

echo "Frames extracted"

# ── Labels ────────────────────────────────────────────────────────────────
# Convert float timestamps to zero-padded integer seconds
TS1=$(printf "%02d" "${T1%.*}")
TS2=$(printf "%02d" "${T2%.*}")
TS3=$(printf "%02d" "${T3%.*}")
TS4=$(printf "%02d" "${T4%.*}")

label_frame() {
  local SRC="$1"
  local DST="$2"
  local LABEL="$3"

  if [ "$SKIP_LABELS" -eq 1 ]; then
    # No font available — copy frame unlabelled so collage can still proceed
    cp "$SRC" "$DST"
    return
  fi

  ffmpeg -y -i "$SRC" \
    -vf "drawbox=x=10:y=10:w=iw-20:h=60:color=black@0.65:t=fill,\
drawtext=fontfile='${FONT}':text='${LABEL}':x=20:y=20:fontsize=28:fontcolor=white" \
    -update 1 "$DST"
}

label_frame "$FRAME1" "$LABELED1" "${CAMERA} - 00:${TS1}"
label_frame "$FRAME2" "$LABELED2" "${CAMERA} - 00:${TS2}"
label_frame "$FRAME3" "$LABELED3" "${CAMERA} - 00:${TS3}"
label_frame "$FRAME4" "$LABELED4" "${CAMERA} - 00:${TS4}"

echo "Labels added"

# ── 2×2 collage ───────────────────────────────────────────────────────────
# scale=-2 (not -1) ensures dimensions stay even-numbered for jpeg encoding
ffmpeg -y \
  -i "$LABELED1" \
  -i "$LABELED2" \
  -i "$LABELED3" \
  -i "$LABELED4" \
  -filter_complex "\
[0:v]scale=640:-2[a]; \
[1:v]scale=640:-2[b]; \
[2:v]scale=640:-2[c]; \
[3:v]scale=640:-2[d]; \
[a][b]hstack=inputs=2[top]; \
[c][d]hstack=inputs=2[bottom]; \
[top][bottom]vstack=inputs=2" \
  "$COLLAGE"

echo "Collage created:"
ls -lah "$COLLAGE"

# ── Cleanup ───────────────────────────────────────────────────────────────
rm -f "$LOCAL_CLIP" "$FRAME1" "$FRAME2" "$FRAME3" "$FRAME4"
rm -f "$LABELED1" "$LABELED2" "$LABELED3" "$LABELED4"

echo "==== DONE ===="
