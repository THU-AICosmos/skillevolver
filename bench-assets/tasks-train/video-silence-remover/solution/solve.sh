#!/bin/bash
set -e

# Solution for video dead-air trimmer
# Pipeline:
#   audio extraction → energy analysis → dead-air detection → video trimming → edit log

SRC="data/input_video.mp4"
OUT_VID="trimmed_lecture.mp4"
OUT_LOG="edit_log.json"
TMP="/tmp/trimmer"
mkdir -p "$TMP"

echo ">>> Dead Air Trimmer — starting <<<"

# ---- Extract mono 16 kHz audio ----
echo "[1/5] Extracting audio track..."
python3 /root/.claude/skills/audio-extractor/scripts/extract_audio.py \
    --video "$SRC" --sample-rate 16000 --output "$TMP/mono.wav"

# ---- Compute per-second RMS energy ----
echo "[2/5] Computing energy profile..."
python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
    --audio "$TMP/mono.wav" --window-seconds 1 --output "$TMP/rms.json"

# ---- Detect intro dead air ----
echo "[3/5] Locating intro dead air..."
python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
    --energies "$TMP/rms.json" \
    --threshold-multiplier 1.7 \
    --initial-window 60 \
    --smoothing-window 30 \
    --output "$TMP/intro.json"

INTRO_END=$(python3 -c "
import json, sys
segs = json.load(open('$TMP/intro.json'))['segments']
print(segs[0]['end'] if segs else 0)
")
echo "   intro ends at ${INTRO_END}s"

# ---- Detect mid-lecture pauses ----
echo "[4/5] Scanning for pauses after intro..."
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies "$TMP/rms.json" \
    --start-time "$INTRO_END" \
    --threshold-ratio 0.55 \
    --min-duration 2 \
    --window-size 30 \
    --output "$TMP/pauses.json"

# ---- Merge all detected segments ----
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments "$TMP/intro.json" "$TMP/pauses.json" \
    --output "$TMP/merged.json"

# ---- Trim the video ----
echo "[5/5] Trimming video..."
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input "$SRC" --output "$OUT_VID" --remove-segments "$TMP/merged.json"

# ---- Build edit log (different JSON schema from report-generator) ----
python3 - "$SRC" "$OUT_VID" "$TMP/merged.json" "$OUT_LOG" <<'PYEOF'
import json, subprocess, sys

src_vid, out_vid, seg_file, log_file = sys.argv[1:]

def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

src_dur = duration(src_vid)
out_dur = duration(out_vid)

with open(seg_file) as f:
    all_segs = json.load(f)["segments"]

cuts = []
for s in sorted(all_segs, key=lambda x: x["start"]):
    cuts.append({
        "from_sec": round(s["start"], 2),
        "to_sec": round(s["end"], 2),
        "length_sec": round(s["end"] - s["start"], 2),
    })

dead_air = round(sum(c["length_sec"] for c in cuts), 2)

log = {
    "source_length_sec": round(src_dur, 2),
    "output_length_sec": round(out_dur, 2),
    "dead_air_total_sec": round(dead_air, 2),
    "cut_ratio_percent": round(dead_air / src_dur * 100, 2),
    "cuts": cuts,
}

with open(log_file, "w") as f:
    json.dump(log, f, indent=2)

print(f"Edit log written: {log_file}")
PYEOF

echo ">>> Done — outputs: $OUT_VID, $OUT_LOG <<<"
