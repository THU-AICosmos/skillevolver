#!/bin/bash
set -e

# Lecture Video Content Analyzer - Solution
# Pipeline: extract audio -> analyze energy -> find non-content intervals -> trim video -> write report

SRC_VIDEO="data/input_video.mp4"
TRIMMED_VIDEO="trimmed_lecture.mp4"
ANALYSIS_REPORT="content_analysis.json"

TMPDIR_WORK="/tmp/content_analysis"
mkdir -p "$TMPDIR_WORK"

echo "=== Lecture Video Content Analyzer ==="

# --- Phase 1: Audio extraction and energy analysis ---
echo "Phase 1: Extracting audio and computing energy profile..."
python3 /root/.claude/skills/audio-extractor/scripts/extract_audio.py \
    --video "$SRC_VIDEO" \
    --sample-rate 16000 \
    --output "$TMPDIR_WORK/raw_audio.wav"

python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
    --audio "$TMPDIR_WORK/raw_audio.wav" \
    --window-seconds 1 \
    --output "$TMPDIR_WORK/energy_profile.json"

# --- Phase 2: Detect non-content intervals (intro + pauses) ---
echo "Phase 2: Detecting non-content intervals..."

# Detect the intro/title-card segment
python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
    --energies "$TMPDIR_WORK/energy_profile.json" \
    --threshold-multiplier 1.7 \
    --initial-window 60 \
    --smoothing-window 30 \
    --output "$TMPDIR_WORK/intro_segment.json"

# Find where the intro ends
INTRO_END=$(python3 -c "
import json
segs = json.load(open('$TMPDIR_WORK/intro_segment.json'))['segments']
print(segs[0]['end'] if segs else 0)
")
echo "Intro ends at: ${INTRO_END}s"

# Detect dead-air pauses after the intro
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies "$TMPDIR_WORK/energy_profile.json" \
    --start-time "$INTRO_END" \
    --threshold-ratio 0.55 \
    --min-duration 2 \
    --window-size 30 \
    --output "$TMPDIR_WORK/dead_air.json"

# Merge all non-content intervals
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments "$TMPDIR_WORK/intro_segment.json" "$TMPDIR_WORK/dead_air.json" \
    --output "$TMPDIR_WORK/all_non_content.json"

# --- Phase 3: Trim video and generate analysis report ---
echo "Phase 3: Trimming video and generating report..."

python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input "$SRC_VIDEO" \
    --output "$TRIMMED_VIDEO" \
    --remove-segments "$TMPDIR_WORK/all_non_content.json"

# Generate the analysis report with the required field names
python3 /root/.claude/skills/report-generator/scripts/generate_report.py \
    --original "$SRC_VIDEO" \
    --compressed "$TRIMMED_VIDEO" \
    --segments "$TMPDIR_WORK/all_non_content.json" \
    --output "$TMPDIR_WORK/raw_report.json"

# Convert the report format to match our required schema
python3 -c "
import json

raw = json.load(open('$TMPDIR_WORK/raw_report.json'))

# Read segments and convert field names
segments_raw = raw.get('segments_removed', [])
intervals = []
for seg in segments_raw:
    intervals.append({
        'from': seg['start'],
        'to': seg['end'],
        'length': seg['duration']
    })

analysis = {
    'source_length_sec': raw['original_duration_seconds'],
    'trimmed_length_sec': raw['compressed_duration_seconds'],
    'cut_total_sec': raw['removed_duration_seconds'],
    'cut_ratio_pct': raw['compression_percentage'],
    'non_content_intervals': intervals
}

with open('$ANALYSIS_REPORT', 'w') as f:
    json.dump(analysis, f, indent=2)
"

echo "=== Analysis Complete ==="
echo "Outputs:"
echo "  - $TRIMMED_VIDEO"
echo "  - $ANALYSIS_REPORT"
