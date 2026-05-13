#!/usr/bin/env python3
"""Build a transit-log spreadsheet of non-pedestrian moving entities per video.

Class-based organization:
  - VideoClip            : descriptor for one video file in the input directory.
  - GeminiTallyEngine    : wraps Gemini upload + count-extraction.
  - TransitLogBuilder    : orchestrates the per-clip pass and writes the workbook.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

INPUT_DIR = Path("/app/video")
REPORT_PATH = INPUT_DIR / "transit_log.xlsx"
SHEET_LABEL = "tally"
HEADERS = ("clip", "non_pedestrian_count")
VIDEO_SUFFIXES = (".mp4", ".mkv", ".avi", ".mov", ".wmv",
                  ".flv", ".webm", ".m4v", ".mpeg", ".mpg", ".3gpp")

PROMPT = (
    "You are reviewing a fixed surveillance camera shot of a public street. "
    "Count every distinct NON-PEDESTRIAN moving entity in the clip.\n\n"
    "What counts as a single non-pedestrian entity:\n"
    "  - A motor vehicle (car / van / truck / bus) — count it as 1, regardless "
    "    of how many occupants are inside.\n"
    "  - A bicycle, e-bike, scooter, or motorcycle being ridden — count the "
    "    rider+vehicle together as 1 entity, not as a separate person.\n"
    "  - A parked or stationary vehicle on the street still counts as 1.\n\n"
    "What does NOT count:\n"
    "  - People walking on foot (pedestrians).\n\n"
    "If the same vehicle / cyclist appears across many consecutive frames, "
    "still only count it once.\n\n"
    "Reason briefly, then output your final integer wrapped in answer tags, "
    "e.g. <answer>4</answer>."
)


@dataclass(frozen=True)
class VideoClip:
    name: str
    path: Path

    @classmethod
    def discover(cls, directory: Path) -> list["VideoClip"]:
        items: list[VideoClip] = []
        for entry in sorted(directory.iterdir()):
            if entry.is_file() and entry.suffix.lower() in VIDEO_SUFFIXES:
                items.append(cls(name=entry.name, path=entry))
        return items


class GeminiTallyEngine:
    """Thin wrapper around google-genai for video-question answering."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def _await_ready(self, handle, deadline_s: int = 300):
        waited = 0
        while handle.state.name == "PROCESSING" and waited < deadline_s:
            time.sleep(5)
            waited += 5
            handle = self._client.files.get(name=handle.name)
        if handle.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini upload not active: state={handle.state.name}")
        return handle

    def tally(self, clip: VideoClip) -> int:
        upload = self._client.files.upload(file=str(clip.path))
        upload = self._await_ready(upload)
        result = self._client.models.generate_content(
            model=self._model,
            contents=[PROMPT, upload],
        )
        text = (result.text or "").strip()
        match = re.search(r"<answer>\s*(\d+)\s*</answer>", text, re.IGNORECASE)
        if not match:
            print(f"  [warn] {clip.name}: no <answer> tag in response: {text!r}")
            return 0
        return int(match.group(1))


class TransitLogBuilder:
    def __init__(self, engine: GeminiTallyEngine, clips: Iterable[VideoClip]):
        self._engine = engine
        self._clips = list(clips)

    def run(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for idx, clip in enumerate(self._clips, 1):
            print(f"[{idx}/{len(self._clips)}] {clip.name}")
            try:
                count = self._engine.tally(clip)
            except Exception as exc:
                print(f"  [error] {clip.name}: {exc}")
                count = 0
            print(f"  -> non_pedestrian_count = {count}")
            tallies[clip.name] = count
        return tallies

    @staticmethod
    def write_workbook(tallies: dict[str, int], destination: Path) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_LABEL
        ws.append(list(HEADERS))
        for clip_name in sorted(tallies):
            ws.append([clip_name, tallies[clip_name]])
        destination.parent.mkdir(parents=True, exist_ok=True)
        wb.save(destination)
        print(f"Wrote transit log: {destination}")


def _entry() -> int:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
        return 2

    if not INPUT_DIR.is_dir():
        print(f"ERROR: input dir missing: {INPUT_DIR}", file=sys.stderr)
        return 2

    clips = VideoClip.discover(INPUT_DIR)
    if not clips:
        print(f"ERROR: no video files in {INPUT_DIR}", file=sys.stderr)
        return 2

    print(f"Transit log build  |  clips={len(clips)}")
    engine = GeminiTallyEngine(api_key)
    builder = TransitLogBuilder(engine, clips)
    tallies = builder.run()
    builder.write_workbook(tallies, REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(_entry())
