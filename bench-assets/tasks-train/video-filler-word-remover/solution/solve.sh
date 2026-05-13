#!/bin/bash
set -e

# Step 1 — extract mono 16 kHz audio for the transcription API
ffmpeg -i /root/input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /root/speech.wav -y 2>/dev/null

# Step 2 — call OpenAI Whisper to get word-level timestamps, then
#           scan for hesitation markers and write the two output files
python3 << 'PYEOF'
import json, os, urllib.request, urllib.error, collections

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("OPENAI_API_KEY is not set")

# ── Whisper API request (multipart/form-data) ──────────────────────
BOUNDARY = "---Boundary9876543210"

def build_multipart(wav_path):
    parts = []
    for name, value in [("model", "whisper-1"),
                        ("response_format", "verbose_json"),
                        ("timestamp_granularities[]", "word")]:
        parts += [f"--{BOUNDARY}".encode(),
                  f'Content-Disposition: form-data; name="{name}"'.encode(),
                  b"", value.encode()]
    with open(wav_path, "rb") as fh:
        audio = fh.read()
    parts += [f"--{BOUNDARY}".encode(),
              b'Content-Disposition: form-data; name="file"; filename="speech.wav"',
              b"Content-Type: audio/wav", b"", audio,
              f"--{BOUNDARY}--".encode(), b""]
    return b"\r\n".join(parts)

body = build_multipart("/root/speech.wav")
req = urllib.request.Request(
    "https://api.openai.com/v1/audio/transcriptions",
    data=body, method="POST",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
    },
)
try:
    with urllib.request.urlopen(req) as resp:
        transcript = json.loads(resp.read().decode())
except urllib.error.HTTPError as exc:
    raise SystemExit(f"Whisper API error {exc.code}: {exc.read().decode()}")

# ── Filler-phrase detection ─────────────────────────────────────────
SINGLE_FILLERS = {"um", "uh", "hum", "hmm", "mhm",
                  "like", "yeah", "so", "basically", "well", "okay"}
MULTI_FILLERS = {"you know", "i mean", "kind of", "i guess"}

words = transcript.get("words", [])
detections = []

# single-word scan
for w in words:
    token = w["word"].strip().lower()
    if token in SINGLE_FILLERS:
        detections.append({"phrase": token, "start_time": round(w["start"], 2)})

# two-word scan
for idx in range(len(words) - 1):
    pair = (words[idx]["word"].strip() + " " + words[idx + 1]["word"].strip()).lower()
    if pair in MULTI_FILLERS:
        detections.append({"phrase": pair, "start_time": round(words[idx]["start"], 2)})

# deduplicate & sort
detections.sort(key=lambda d: d["start_time"])
seen = set()
unique = []
for d in detections:
    key = (d["phrase"], d["start_time"])
    if key not in seen:
        seen.add(key)
        unique.append(d)

with open("/root/detected_fillers.json", "w") as fp:
    json.dump(unique, fp, indent=2)
print(f"Detected {len(unique)} hesitation markers")

# ── Summary report ──────────────────────────────────────────────────
counter = collections.Counter(d["phrase"] for d in unique)
lines = [f"Total filler phrases detected: {len(unique)}",
         "",
         "Breakdown by phrase:"]
for phrase, cnt in counter.most_common():
    lines.append(f"  {phrase}: {cnt}")
lines += ["", f"Distinct filler phrase types: {len(counter)}"]
with open("/root/filler_report.txt", "w") as fp:
    fp.write("\n".join(lines) + "\n")
print("Summary report written to /root/filler_report.txt")
PYEOF

echo "Done — outputs at /root/detected_fillers.json and /root/filler_report.txt"
