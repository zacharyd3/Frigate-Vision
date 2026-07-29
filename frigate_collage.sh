#!/bin/bash
# frigate_collage.sh
#
# Downloads a Frigate event clip, extracts 4 frames at 10/35/60/90% through
# the clip, then assembles them into a single-row (1×4) collage saved to
# /config/www/frigate/. Frames are left unlabelled — overlaying camera name
# and timestamps on top of already-busy frames only makes the collage harder
# for the AI to read.
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

COLLAGE="$WORK_DIR/frigate_event_${CAMERA}_${EVENT_ID}.jpg"

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
ffmpeg -nostdin -y -ss "$T1" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME1"
ffmpeg -nostdin -y -ss "$T2" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME2"
ffmpeg -nostdin -y -ss "$T3" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME3"
ffmpeg -nostdin -y -ss "$T4" -i "$LOCAL_CLIP" -frames:v 1 -update 1 "$FRAME4"

test -f "$FRAME1"
test -f "$FRAME2"
test -f "$FRAME3"
test -f "$FRAME4"

echo "Frames extracted"

# ── Single-row collage ─────────────────────────────────────────────────────
# Frames are stacked left-to-right in chronological order so the AI reads the
# event as a single timeline. scale=-2 (not -1) keeps dimensions even-numbered
# for jpeg encoding.
ffmpeg -nostdin -y \
  -i "$FRAME1" \
  -i "$FRAME2" \
  -i "$FRAME3" \
  -i "$FRAME4" \
  -filter_complex "\
[0:v]scale=640:-2[a]; \
[1:v]scale=640:-2[b]; \
[2:v]scale=640:-2[c]; \
[3:v]scale=640:-2[d]; \
[a][b][c][d]hstack=inputs=4" \
  "$COLLAGE"

echo "Collage created:"
ls -lah "$COLLAGE"

# ── Cleanup ───────────────────────────────────────────────────────────────
rm -f "$LOCAL_CLIP" "$FRAME1" "$FRAME2" "$FRAME3" "$FRAME4"

echo "==== DONE ===="
