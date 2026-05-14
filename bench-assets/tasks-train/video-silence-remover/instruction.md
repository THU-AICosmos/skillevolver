# Lecture Video Content Analyzer

## Goal

Given a ~10 minute lecture recording, your task is to analyze the audio track and identify segments that do not contain meaningful teaching content. These non-content segments include:

1. A static intro/title card at the beginning (often with background noise but no speech)
2. Dead-air gaps during the lecture where the speaker pauses for more than 2 seconds

After identifying these segments, produce a trimmed version of the video that keeps only the actual lecture content, along with a structured JSON analysis report.

## Input

- **Video file**: `data/input_video.mp4`

## Required Outputs

Place the following files in the current working directory:

1. **`trimmed_lecture.mp4`** — The video with all non-content segments cut out.
2. **`content_analysis.json`** — A JSON report with the following schema:

```json
{
    "source_length_sec": <number>,
    "trimmed_length_sec": <number>,
    "cut_total_sec": <number>,
    "cut_ratio_pct": <number>,
    "non_content_intervals": [
        {
            "from": <number>,
            "to": <number>,
            "length": <number>
        }
    ]
}
```

## Guidelines

- The intro/title card should be detected and removed entirely.
- Pauses longer than 2 seconds within the lecture should be cut.
- Actual spoken content must be preserved.
- You may use ffmpeg, Python, or any other tools available in the environment.
- Processing should complete within a reasonable time frame.

## How Your Output Will Be Checked

1. Whether both output files exist and are valid
2. Whether the reported source duration matches the actual input video
3. Whether the detected non-content intervals are properly ordered and non-overlapping
4. Whether the trimmed video duration falls within an expected range
