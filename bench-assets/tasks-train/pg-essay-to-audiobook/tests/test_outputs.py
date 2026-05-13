"""Tests for wikipedia-to-podcast task.

Evaluation:
- Deterministic: file exists, size, duration
- WER-based: transcribe full audio via OpenAI Whisper API and calculate WER against all articles
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

OUTPUT_FILE = "/root/podcast.mp3"

WIKI_ARTICLES = [
    ("Alan_Turing", "Alan Turing"),
    ("Grace_Hopper", "Grace Hopper"),
    ("Ada_Lovelace", "Ada Lovelace"),
]

REQ_HEADERS = {"User-Agent": "PodcastTestBot/1.0 (educational project)"}


@pytest.fixture(scope="module")
def mp3_path():
    """Load audio file path (implicitly tests existence)."""
    p = Path(OUTPUT_FILE)
    assert p.exists(), f"Output not found: {OUTPUT_FILE}"
    return p


def probe_duration(fpath):
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(fpath),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return float(proc.stdout.strip())
    return 0


def grab_wiki_lead(slug):
    """Fetch lead section text from Wikipedia MediaWiki API."""
    import requests

    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": slug.replace("_", " "),
        "prop": "extracts",
        "exintro": "true",
        "explaintext": "true",
        "format": "json",
    }
    resp = requests.get(api_url, params=params, headers=REQ_HEADERS, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        extract = page_data.get("extract", "")
        extract = re.sub(r"\s+", " ", extract).strip()
        return extract.lower()
    return ""


def clean_for_wer(text):
    """Normalize text for WER calculation."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def test_podcast_file_exists(mp3_path):
    """Podcast audio file should exist."""
    assert mp3_path.exists(), "podcast.mp3 not found"


def test_podcast_file_size(mp3_path):
    """Audio file should be substantial (> 1MB for 3 articles)."""
    size_mb = mp3_path.stat().st_size / (1024 * 1024)
    assert size_mb > 1, f"Audio file too small: {size_mb:.2f}MB (expected > 1MB)"


def test_podcast_duration(mp3_path):
    """Audio should be at least 4 minutes for 3 Wikipedia lead sections."""
    dur = probe_duration(mp3_path)
    min_dur = 4 * 60  # 4 minutes minimum
    assert dur > min_dur, f"Audio too short: {dur / 60:.1f} min (expected > 4 min)"


def test_podcast_wer():
    """Transcribe audio via OpenAI Whisper and check WER against original articles."""
    from jiwer import wer
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    if not Path(OUTPUT_FILE).exists():
        pytest.fail("podcast.mp3 not found")

    dur = probe_duration(OUTPUT_FILE)
    if dur < 240:
        pytest.skip("Audio too short for WER test")

    # Split audio into chunks for Whisper API (max 25MB per request)
    chunk_len = 600  # 10 min chunks
    n_chunks = int(dur / chunk_len) + 1

    transcribed_parts = []
    print(f"\nTranscribing {dur / 60:.1f} minutes of audio in {n_chunks} chunks...")

    client = OpenAI(api_key=api_key)

    for idx in range(n_chunks):
        offset = idx * chunk_len
        chunk_path = f"/tmp/wer_part_{idx}.mp3"

        cmd = [
            "ffmpeg", "-y", "-i", OUTPUT_FILE,
            "-ss", str(offset), "-t", str(chunk_len),
            "-c", "copy", chunk_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        if not Path(chunk_path).exists():
            continue

        print(f"  Transcribing chunk {idx + 1}/{n_chunks}...")
        try:
            with open(chunk_path, "rb") as f:
                result = client.audio.transcriptions.create(model="whisper-1", file=f)
            transcribed_parts.append(result.text)
        except Exception as exc:
            print(f"  Failed to transcribe chunk {idx + 1}: {exc}")
        finally:
            Path(chunk_path).unlink(missing_ok=True)

    if not transcribed_parts:
        pytest.fail("Failed to transcribe any audio chunks")

    full_transcript = clean_for_wer(" ".join(transcribed_parts))
    print(f"\nTranscript length: {len(full_transcript)} chars")
    print(f"Transcript preview: {full_transcript[:300]}...")

    # Fetch original article texts
    print("\nFetching original Wikipedia articles...")
    originals = []
    for slug, title in WIKI_ARTICLES:
        try:
            text = grab_wiki_lead(slug)
            originals.append(text)
            print(f"  Fetched {title}: {len(text)} chars")
        except Exception as exc:
            print(f"  Failed to fetch {title}: {exc}")

    if not originals:
        pytest.fail("Could not fetch any original articles")

    combined_ref = clean_for_wer(" ".join(originals))
    print(f"\nCombined reference length: {len(combined_ref)} chars")

    try:
        score = wer(combined_ref, full_transcript)
    except Exception as exc:
        pytest.fail(f"WER calculation failed: {exc}")

    print(f"\nWER score: {score:.2%}")

    threshold = 0.30  # 30% WER threshold
    assert score < threshold, (
        f"WER too high: {score:.2%} (threshold: {threshold:.0%}). "
        "Audio may not match article content."
    )
