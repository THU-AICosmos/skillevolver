#!/bin/bash
set -e

# Step 1 — extract mono 16 kHz WAV from the source video
ffmpeg -i /root/input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /root/audio.wav -y 2>/dev/null

# Step 2 — transcribe with Whisper API and locate filler words
python3 << 'DETECT_FILLERS'
import json, os, urllib.request, urllib.error

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is required")

boundary = "----Boundary9876543210"

def build_multipart(wav_path):
    parts = []
    def field(name, value):
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        parts.append(b"")
        parts.append(value.encode() if isinstance(value, str) else value)

    field("model", "whisper-1")
    field("response_format", "verbose_json")
    field("timestamp_granularities[]", "word")

    with open(wav_path, "rb") as f:
        audio_bytes = f.read()
    parts.append(f"--{boundary}".encode())
    parts.append(b'Content-Disposition: form-data; name="file"; filename="audio.wav"')
    parts.append(b"Content-Type: audio/wav")
    parts.append(b"")
    parts.append(audio_bytes)
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    return b"\r\n".join(parts)

body = build_multipart("/root/audio.wav")
req = urllib.request.Request(
    "https://api.openai.com/v1/audio/transcriptions",
    data=body, method="POST",
)
req.add_header("Authorization", f"Bearer {api_key}")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

try:
    with urllib.request.urlopen(req) as resp:
        transcript = json.loads(resp.read().decode())
except urllib.error.HTTPError as exc:
    print(f"Whisper API error {exc.code}: {exc.read().decode()}")
    raise

# --- filler detection ---
SINGLE = {"um", "uh", "hum", "hmm", "mhm", "like", "yeah", "so",
           "basically", "well", "okay"}
MULTI  = ["you know", "i mean", "kind of", "i guess"]

words = transcript.get("words", [])
detected = []

for w in words:
    tok = w["word"].strip().lower()
    if tok in SINGLE:
        detected.append({"filler": tok, "start_time": round(w["start"], 2)})

for idx in range(len(words) - 1):
    pair = (words[idx]["word"].strip() + " " + words[idx+1]["word"].strip()).lower()
    if pair in MULTI:
        detected.append({"filler": pair, "start_time": round(words[idx]["start"], 2)})

# deduplicate & sort
detected.sort(key=lambda d: d["start_time"])
seen = set()
unique = []
for d in detected:
    k = (d["filler"], d["start_time"])
    if k not in seen:
        seen.add(k)
        unique.append(d)

with open("/root/detected_fillers.json", "w") as fp:
    json.dump(unique, fp, indent=2)
print(f"Found {len(unique)} filler instances")
DETECT_FILLERS

# Step 3 — build the cleaned video (non-filler segments only)
python3 << 'BUILD_CLEAN'
import json, subprocess, os

with open("/root/detected_fillers.json") as fp:
    fillers = json.load(fp)

dur_result = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", "/root/input.mp4"],
    capture_output=True, text=True)
total_duration = float(dur_result.stdout.strip())

# Estimate per-filler duration
FILLER_LEN = {
    "uh": 0.3, "um": 0.4, "hum": 0.6, "hmm": 0.6, "mhm": 0.55,
    "like": 0.3, "yeah": 0.35, "so": 0.25, "well": 0.35, "okay": 0.4,
    "basically": 0.55, "you know": 0.55, "i mean": 0.5,
    "kind of": 0.5, "i guess": 0.5,
}
PAD = 0.05

cuts = []
for f in fillers:
    w = f["filler"].lower().strip()
    t = f["start_time"]
    length = FILLER_LEN.get(w, 0.4)
    cuts.append((max(0, t - PAD), t + length))

# merge overlapping cut regions
if cuts:
    cuts.sort()
    merged = [cuts[0]]
    for s, e in cuts[1:]:
        ps, pe = merged[-1]
        if s <= pe + 0.1:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
else:
    merged = []

# Compute keep-segments (inverse of cuts)
keeps = []
pos = 0.0
for cs, ce in merged:
    if cs > pos:
        keeps.append((pos, cs))
    pos = ce
if pos < total_duration:
    keeps.append((pos, total_duration))

print(f"Keeping {len(keeps)} segments, removing {len(merged)} filler regions")

# Extract each keep-segment
parts = []
for i, (s, e) in enumerate(keeps):
    out = f"/tmp/keep_{i:04d}.ts"
    subprocess.run([
        "ffmpeg", "-y", "-i", "/root/input.mp4",
        "-ss", str(s), "-to", str(e),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k", out
    ], check=True, capture_output=True)
    parts.append(out)

concat_list = "/tmp/keep_concat.txt"
with open(concat_list, "w") as cl:
    for p in parts:
        cl.write(f"file '{p}'\n")

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_list, "-c", "copy", "/root/cleaned.mp4"
], check=True, capture_output=True)

# tidy up
for p in parts:
    os.remove(p)
os.remove(concat_list)

cleaned_dur = float(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", "/root/cleaned.mp4"],
    capture_output=True, text=True).stdout.strip())
print(f"Input: {total_duration:.1f}s  →  Cleaned: {cleaned_dur:.1f}s")
BUILD_CLEAN

echo "Done – cleaned video at /root/cleaned.mp4"
