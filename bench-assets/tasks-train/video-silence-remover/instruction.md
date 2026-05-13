# Video Dead Air Trimmer

## Goal

Given an educational lecture recording (~10 minutes), your job is to detect and cut out "dead air" — periods where no meaningful audio is present. These typically include:

1. A static intro screen at the beginning (often with background hiss but no speech)
2. Extended gaps of silence between lecture segments (gaps longer than 2 seconds)

Produce a trimmed version of the video and a structured JSON log describing what was cut.

## Input

- **Source recording**: `data/input_video.mp4`

## Required Outputs

Place the following two files in the working directory (`/root`):

### 1. `trimmed_lecture.mp4`
The video with all detected dead air segments removed, keeping all speech/teaching content intact.

### 2. `edit_log.json`
A JSON file documenting the edits made. Format:

```json
{
  "source_length_sec": <number>,
  "output_length_sec": <number>,
  "dead_air_total_sec": <number>,
  "cut_ratio_percent": <number>,
  "cuts": [
    {
      "from_sec": <number>,
      "to_sec": <number>,
      "length_sec": <number>
    }
  ]
}
```

## Guidelines

- The intro screen (dead air before any speech begins) must be detected and removed.
- Pauses longer than ~2 seconds within the lecture should be removed.
- All actual teaching/speech content should be preserved.
- You may use ffmpeg, Python, or any available tools.
- Processing should complete within a reasonable time frame (under 10 minutes).

## How Your Output Will Be Judged

1. Whether the trimmed video exists and is playable
2. Whether detected cut segments align with known dead air locations (precision)
3. Whether the trimmed video duration is in the expected range
4. Whether the audio in the trimmed video corresponds to what the edit log describes
