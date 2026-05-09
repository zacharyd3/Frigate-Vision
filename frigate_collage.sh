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

echo "==== START ===="
echo "Downloading clip..."

curl -L "$CLIP_URL" -o "$LOCAL_CLIP"

echo "Downloaded:"
ls -lah "$LOCAL_CLIP"

# Validate file exists
test -f "$LOCAL_CLIP"

# Get duration
DURATION=$(ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  "$LOCAL_CLIP")

echo "Duration: $DURATION"

if [ -z "$DURATION" ]; then
  echo "ERROR: Could not determine clip duration"
  exit 1
fi

# Timestamps at 10 / 35 / 60 / 90 % through the clip
T1=$(awk "BEGIN {print $DURATION * 0.1}")
T2=$(awk "BEGIN {print $DURATION * 0.35}")
T3=$(awk "BEGIN {print $DURATION * 0.6}")
T4=$(awk "BEGIN {print $DURATION * 0.9}")

echo "Extracting frames at: $T1  $T2  $T3  $T4"

# Extract frames
ffmpeg -y -ss "$T1" -i "$LOCAL_CLIP" -frames:v 1 "$FRAME1"
ffmpeg -y -ss "$T2" -i "$LOCAL_CLIP" -frames:v 1 "$FRAME2"
ffmpeg -y -ss "$T3" -i "$LOCAL_CLIP" -frames:v 1 "$FRAME3"
ffmpeg -y -ss "$T4" -i "$LOCAL_CLIP" -frames:v 1 "$FRAME4"

# Verify extraction succeeded
test -f "$FRAME1"
test -f "$FRAME2"
test -f "$FRAME3"
test -f "$FRAME4"

echo "Frames extracted"

# Convert float timestamps to zero-padded seconds for labels
TS1=$(printf "%02d" "${T1%.*}")
TS2=$(printf "%02d" "${T2%.*}")
TS3=$(printf "%02d" "${T3%.*}")
TS4=$(printf "%02d" "${T4%.*}")

# Stamp each frame with camera name and timestamp
ffmpeg -y -i "$FRAME1" \
  -vf "drawbox=x=10:y=10:w=340:h=55:color=black@0.6:t=fill,drawtext=text='${CAMERA} - 00\:${TS1}':x=20:y=20:fontsize=28:fontcolor=white" \
  "$LABELED1"

ffmpeg -y -i "$FRAME2" \
  -vf "drawbox=x=10:y=10:w=340:h=55:color=black@0.6:t=fill,drawtext=text='${CAMERA} - 00\:${TS2}':x=20:y=20:fontsize=28:fontcolor=white" \
  "$LABELED2"

ffmpeg -y -i "$FRAME3" \
  -vf "drawbox=x=10:y=10:w=340:h=55:color=black@0.6:t=fill,drawtext=text='${CAMERA} - 00\:${TS3}':x=20:y=20:fontsize=28:fontcolor=white" \
  "$LABELED3"

ffmpeg -y -i "$FRAME4" \
  -vf "drawbox=x=10:y=10:w=340:h=55:color=black@0.6:t=fill,drawtext=text='${CAMERA} - 00\:${TS4}':x=20:y=20:fontsize=28:fontcolor=white" \
  "$LABELED4"

echo "Labels added"

# Assemble 2×2 collage
ffmpeg -y \
  -i "$LABELED1" \
  -i "$LABELED2" \
  -i "$LABELED3" \
  -i "$LABELED4" \
  -filter_complex "\
[0:v]scale=640:-1[a]; \
[1:v]scale=640:-1[b]; \
[2:v]scale=640:-1[c]; \
[3:v]scale=640:-1[d]; \
[a][b]hstack=inputs=2[top]; \
[c][d]hstack=inputs=2[bottom]; \
[top][bottom]vstack=inputs=2" \
  "$COLLAGE"

echo "Collage created:"
ls -lah "$COLLAGE"

# Cleanup intermediates
rm -f "$LOCAL_CLIP" "$FRAME1" "$FRAME2" "$FRAME3" "$FRAME4"
rm -f "$LABELED1" "$LABELED2" "$LABELED3" "$LABELED4"

echo "==== DONE ===="
