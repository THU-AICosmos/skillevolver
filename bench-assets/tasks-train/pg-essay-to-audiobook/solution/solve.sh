#!/bin/bash
set -e

pip install --break-system-packages requests==2.32.3 openai==1.58.1 pydub==0.25.1 gTTS==2.5.3 -q

cat > /tmp/build_podcast.py << 'PYEOF'
import os
import re
import time
import tempfile
import requests
from pathlib import Path
from pydub import AudioSegment

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

ARTICLES = [
    ("Alan_Turing", "Alan Turing"),
    ("Grace_Hopper", "Grace Hopper"),
    ("Ada_Lovelace", "Ada Lovelace"),
]

DEST = "/root/podcast.mp3"

HEADERS = {"User-Agent": "PodcastBot/1.0 (educational project)"}


def extract_lead_section(slug, retries=3):
    """Pull introductory text from Wikipedia MediaWiki API."""
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": slug.replace("_", " "),
        "prop": "extracts",
        "exintro": "true",
        "explaintext": "true",
        "format": "json",
    }

    for attempt in range(retries):
        try:
            r = requests.get(api_url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                extract = page_data.get("extract", "")
                extract = re.sub(r"\s+", " ", extract).strip()
                return extract
            return ""
        except requests.exceptions.RequestException as exc:
            if attempt < retries - 1:
                print(f"  Retry {attempt + 1}/{retries} for {slug}: {exc}")
                time.sleep(2 ** attempt)
            else:
                raise


def split_at_sentences(text, limit=4000):
    """Chop text into sentence-boundary-aware segments."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    segments, current = [], ""
    for s in sentences:
        if len(current) + len(s) < limit:
            current += s + " "
        else:
            if current:
                segments.append(current.strip())
            current = s + " "
    if current:
        segments.append(current.strip())
    return segments


def speak_openai(client, segment_text, out_path, retries=3):
    """Call OpenAI TTS endpoint with retry."""
    for attempt in range(retries):
        try:
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="onyx",
                input=segment_text,
            ) as resp:
                resp.stream_to_file(out_path)
            return True
        except Exception as exc:
            delay = 5 * (2 ** attempt)
            print(f"  TTS retry {attempt + 1}/{retries}: {exc} (wait {delay}s)")
            time.sleep(delay)
    return False


def speak_gtts(segment_text, out_path):
    """Use gTTS as free fallback."""
    from gtts import gTTS
    tts = gTTS(text=segment_text, lang="en", slow=False)
    tts.save(out_path)
    return True


def run():
    use_openai = bool(OPENAI_KEY)
    client = None
    if use_openai:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        print("Using OpenAI TTS")
    else:
        print("Using gTTS (free fallback)")

    collected_segments = []

    for slug, label in ARTICLES:
        print(f"Fetching: {label}")
        body = extract_lead_section(slug)
        print(f"  Got {len(body)} characters")

        header = f"Section: {label}. "
        full = header + body

        pieces = split_at_sentences(full)
        print(f"  Split into {len(pieces)} pieces")

        for idx, piece in enumerate(pieces):
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_file = tf.name

            print(f"  Generating piece {idx + 1}/{len(pieces)}...")

            ok = False
            if use_openai:
                ok = speak_openai(client, piece, tmp_file)
            if not ok:
                ok = speak_gtts(piece, tmp_file)

            if ok:
                try:
                    seg = AudioSegment.from_mp3(tmp_file)
                    collected_segments.append(seg)
                except Exception as exc:
                    print(f"  Could not load piece {idx + 1}: {exc}")
                finally:
                    os.unlink(tmp_file)
            else:
                print(f"  Failed piece {idx + 1}")

    if not collected_segments:
        print("No audio generated!")
        return

    print(f"Merging {len(collected_segments)} segments...")
    merged = collected_segments[0]
    for s in collected_segments[1:]:
        merged += s

    merged.export(DEST, format="mp3")
    print(f"Done! Saved to {DEST}")


if __name__ == "__main__":
    run()
PYEOF

python3 /tmp/build_podcast.py
