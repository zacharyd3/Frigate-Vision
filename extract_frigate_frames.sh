#!/bin/bash
# extract_frigate_frames.sh
#
# Lightweight alternative to frigate_collage.sh — extracts 3 frames from a
# Frigate event clip (at 20/50/80%) directly from the remote URL without
# downloading the full clip first.  No collage is built; frames are saved
# individually for use in other workflows.
#
# Usage:
#   extract_frigate_frames.sh "<clip_url>" "<event_id>"
#
# Output:
#   /config/www/frigate/<event_id>_1.jpg
#   /config/www/frigate/<event_id>_2.jpg
#   /config/www/frigate/<event_id>_3.jpg
#
# Requirements:
#   - ffmpeg / ffprobe

OUTPUT_DIR="/config/www/frigate"

CLIP_URL="$1"
EVENT_ID="$2"

mkdir -p "$OUTPUT_DIR"

# Probe duration directly from the remote URL
DURATION=$(ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  "$CLIP_URL")

# Strip decimal part
DURATION=${DURATION%.*}

if [ -z "$DURATION" ]; then
  echo "ERROR: Could not determine clip duration"
  exit 1
fi

# Timestamps at 20 / 50 / 80 %
T1=$((DURATION * 20 / 100))
T2=$((DURATION * 50 / 100))
T3=$((DURATION * 80 / 100))

echo "Duration: $DURATION  |  Frames at: $T1s  $T2s  $T3s"

# Extract frames
ffmpeg -y -ss "$T1" -i "$CLIP_URL" -vframes 1 "$OUTPUT_DIR/${EVENT_ID}_1.jpg"
ffmpeg -y -ss "$T2" -i "$CLIP_URL" -vframes 1 "$OUTPUT_DIR/${EVENT_ID}_2.jpg"
ffmpeg -y -ss "$T3" -i "$CLIP_URL" -vframes 1 "$OUTPUT_DIR/${EVENT_ID}_3.jpg"

echo "Done — frames saved to $OUTPUT_DIR"
