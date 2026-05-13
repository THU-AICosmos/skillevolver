#!/bin/bash
# Oracle solution for video tutorial milestone locator task
# Task: Locate timestamps for 12 key milestones in a Blender tutorial video

set -e

echo "=== Video Tutorial Milestone Locator ==="
echo "Started: $(date)"

VIDEO="/root/tutorial_video.mp4"
WORKSPACE="/root/workspace"
OUTPUT="/root/video_milestones.json"

pip3 install --break-system-packages openai > /dev/null 2>&1

mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# --- Phase 1: Extract audio and transcribe ---
echo "[Phase 1] Extracting audio and transcribing..."

ffmpeg -i "$VIDEO" -vn -acodec libmp3lame -ar 16000 -ac 1 -b:a 64k extracted_audio.mp3 -y -loglevel error

cat > run_transcription.py << 'PYEOF'
import json
from openai import OpenAI

api = OpenAI()

with open("extracted_audio.mp3", "rb") as af:
    result = api.audio.transcriptions.create(
        model="whisper-1",
        file=af,
        response_format="verbose_json",
        timestamp_granularities=["segment"]
    )

lines = []
for seg in result.segments:
    lines.append(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text.strip()}")

with open("full_transcript.txt", "w") as out:
    out.write("\n".join(lines))

print(f"  Transcribed {len(result.segments)} segments")
PYEOF

python3 run_transcription.py

# --- Phase 2: LLM-based milestone alignment ---
echo "[Phase 2] Aligning milestones via LLM..."

cat > locate_milestones.py << 'PYEOF'
import json, re
from openai import OpenAI

api = OpenAI()

with open("full_transcript.txt") as fh:
    transcript_text = fh.read()

LABELS = [
    "What we'll do",
    "Getting started",
    "Import your plan into Blender",
    "It all starts with a plane",
    "Getting the plan in place",
    "Tracing inner walls",
    "Continue tracing inner walls",
    "Make the floor",
    "Extruding the walls in Z",
    "Fixing face orientation errors",
    "Save As",
    "Great job!",
]

numbered = "\n".join(f"  {i+1}. \"{lbl}\"" for i, lbl in enumerate(LABELS))

query = f"""Below is a timestamped transcript from a Blender floor-plan tutorial video (23 min, 1382 s).

TRANSCRIPT:
{transcript_text}

MILESTONES TO FIND (in order):
{numbered}

For every milestone, identify the second at which the speaker first introduces that particular topic.

Rules:
- "What we'll do" must have timestamp 0.
- "Great job!" is the closing section near the end (~1367 s).
- "Continue tracing inner walls" comes after a short break around 628 s.
- "Save As" is a distinct action near the end, different from any earlier save.
- Return ONLY a JSON array like: [{{"label":"...","timestamp":0}}, ...]
"""

resp = api.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": query}],
    temperature=0.0,
    max_tokens=2000,
)

body = resp.choices[0].message.content.strip()
if "```" in body:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", body)
    if m:
        body = m.group(1)

milestones = json.loads(body)

# Enforce first milestone at 0
if milestones and milestones[0]["timestamp"] != 0:
    milestones[0]["timestamp"] = 0

with open("aligned_milestones.json", "w") as fh:
    json.dump(milestones, fh, indent=2)

print(f"  Located {len(milestones)} milestones")
PYEOF

python3 locate_milestones.py

# --- Phase 3: Assemble final output ---
echo "[Phase 3] Writing final output..."

cat > assemble_output.py << 'PYEOF'
import json

with open("aligned_milestones.json") as fh:
    milestones = json.load(fh)

output = {
    "metadata": {
        "source": "In-Depth Floor Plan Tutorial Part 1",
        "total_duration": 1382
    },
    "milestones": milestones
}

with open("/root/video_milestones.json", "w") as fh:
    json.dump(output, fh, indent=2)

print(f"  Wrote {len(milestones)} milestones to /root/video_milestones.json")
PYEOF

python3 assemble_output.py

echo "=== Done ==="
echo "Finished: $(date)"
