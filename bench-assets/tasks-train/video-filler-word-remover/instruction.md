You are building a speech coaching tool that analyzes interview recordings to identify hesitation patterns. The input recording is located at `/root/input.mp4`.

Your goal is to transcribe the audio and detect the following hesitation markers (filler phrases):
- um, uh, hum, hmm, mhm
- like
- you know
- i mean
- yeah
- so
- kind of
- basically
- I guess
- well
- okay

Save the detection results to `/root/detected_fillers.json` as a JSON array. Each entry must include:
- `phrase`: the filler phrase that was detected
- `start_time`: the timestamp in seconds where it occurs

Example format:
```json
[
  {"phrase": "um", "start_time": 3.5},
  {"phrase": "like", "start_time": 12.2},
  {"phrase": "you know", "start_time": 25.8}
]
```

Additionally, generate a plain-text summary report at `/root/filler_report.txt` containing:
1. The total number of filler phrases detected
2. A breakdown showing how many times each distinct filler phrase appears (one line per phrase type, formatted as `<phrase>: <count>`)
3. The number of distinct filler phrase types found
