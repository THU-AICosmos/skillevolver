A Blender tutorial video is available at `/root/tutorial_video.mp4`. It runs for about 23 minutes and covers building a floor plan from scratch. Your goal is to identify the timestamps (in seconds) for 12 key milestone sections within the video.

The milestones to locate are:

1. What we'll do
2. Getting started
3. Import your plan into Blender
4. It all starts with a plane
5. Getting the plan in place
6. Tracing inner walls
7. Continue tracing inner walls
8. Make the floor
9. Extruding the walls in Z
10. Fixing face orientation errors
11. Save As
12. Great job!

Write the results to `/root/video_milestones.json` in the following structure:

```json
{
  "metadata": {
    "source": "In-Depth Floor Plan Tutorial Part 1",
    "total_duration": 1382
  },
  "milestones": [
    {
      "timestamp": 0,
      "label": "What we'll do"
    },
    {
      "timestamp": 92,
      "label": "Getting started"
    }
  ]
}
```

Constraints:

1. There must be exactly 12 milestones in the output.
2. Each milestone's `label` must match the list above exactly (same text, same order).
3. All `timestamp` values must be integers or floats representing seconds.
4. Timestamps should reflect where each topic genuinely begins in the video's audio.
5. All timestamps must fall within 0–1382 seconds.
