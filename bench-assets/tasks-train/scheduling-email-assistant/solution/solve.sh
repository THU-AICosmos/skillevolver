#!/bin/bash
set -e

python3 << 'PYEOF'
#!/usr/bin/env python3
"""
Consultation Booking Scheduler - Functional approach
Reads booking requests, checks calendar gaps, and sends confirmation emails.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from huggingface_hub import InferenceClient


# ---------------------------------------------------------------------------
# LLM-based request extraction
# ---------------------------------------------------------------------------

def build_extraction_prompt(body, sender):
    return f"""You are a scheduling assistant. Parse this consultation booking email and return ONLY valid JSON.

Email:
{body}

Return this JSON structure:
{{
  "sender": "{sender}",
  "durationHours": <number like 0.5, 1, 1.5, 2>,
  "windowStart": "<HH:MM 24h>",
  "windowEnd": "<HH:MM 24h>",
  "firstDate": "<YYYY-MM-DD>",
  "lastDate": "<YYYY-MM-DD>",
  "tz": "PST"
}}

Return ONLY JSON, nothing else."""


def extract_request_info(llm_client, model_name, email_body, sender_addr):
    prompt = build_extraction_prompt(email_body, sender_addr)
    resp = llm_client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model_name,
        max_tokens=500,
        temperature=0.1,
        top_p=0.9,
    )
    raw = resp.choices[0].message.content.strip()

    # Strip markdown fences if present
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end != -1:
        raw = raw[brace_start : brace_end + 1]

    parsed = json.loads(raw)

    return {
        "sender": parsed.get("sender", sender_addr),
        "durationHours": float(parsed.get("durationHours", 1)),
        "windowStart": parsed.get("windowStart", "09:00"),
        "windowEnd": parsed.get("windowEnd", "17:00"),
        "firstDate": parsed.get("firstDate", datetime.now().strftime("%Y-%m-%d")).split("T")[0],
        "lastDate": parsed.get("lastDate", parsed.get("firstDate", datetime.now().strftime("%Y-%m-%d"))).split("T")[0],
        "tz": parsed.get("tz", "PST"),
    }


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

CAL_SKILL_DIR = os.getenv("CALENDAR_SKILL_PATH", "/root/.claude/skills/google-calendar-skill")
PST = timezone(timedelta(hours=-8))


def list_calendar_events(date_from, date_to, t_start="00:00", t_end="23:59"):
    cmd = [
        "node", "scripts/calendar-events-list.js",
        "--timeMin", f"{date_from}T{t_start}:00-08:00",
        "--timeMax", f"{date_to}T{t_end}:59-08:00",
        "--calendar", "primary",
        "--account", "default",
        "--limit", "100",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=CAL_SKILL_DIR)
    blob = proc.stdout
    i, j = blob.find("{"), blob.rfind("}")
    if i == -1 or j == -1:
        raise RuntimeError(f"No JSON in calendar output: {blob[:200]}")
    data = json.loads(blob[i : j + 1])
    if not data.get("success"):
        raise RuntimeError(f"Calendar query unsuccessful: {data}")

    events = []
    for ev in data.get("events", []):
        if ev.get("status") == "cancelled":
            continue
        s, e = ev.get("start"), ev.get("end")
        if s and e:
            events.append({
                "start": _iso_to_dt(s),
                "end": _iso_to_dt(e),
                "title": ev.get("summary", "Busy"),
            })
    events.sort(key=lambda x: x["start"])
    return events


def _iso_to_dt(val):
    if "T" in val:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    return datetime.strptime(val, "%Y-%m-%d")


def compute_open_slots(req):
    d_start = datetime.strptime(req["firstDate"], "%Y-%m-%d")
    d_end = datetime.strptime(req["lastDate"], "%Y-%m-%d")
    busy = list_calendar_events(req["firstDate"], req["lastDate"], req["windowStart"], req["windowEnd"])
    dur_min = int(req["durationHours"] * 60)
    slots = []
    day = d_start
    while day <= d_end:
        if day.weekday() >= 5:  # skip weekends
            day += timedelta(days=1)
            continue
        ws = datetime.strptime(f"{day:%Y-%m-%d} {req['windowStart']}", "%Y-%m-%d %H:%M").replace(tzinfo=PST)
        we = datetime.strptime(f"{day:%Y-%m-%d} {req['windowEnd']}", "%Y-%m-%d %H:%M").replace(tzinfo=PST)
        day_busy = [b for b in busy if b["start"].date() == ws.date() or b["end"].date() == ws.date()]

        cursor = ws
        while cursor + timedelta(minutes=dur_min) <= we:
            slot_end = cursor + timedelta(minutes=dur_min)
            conflict = False
            for b in day_busy:
                if cursor < b["end"] and slot_end > b["start"]:
                    conflict = True
                    cursor = b["end"]
                    break
            if not conflict:
                slots.append({
                    "start": cursor,
                    "end": slot_end,
                    "date": cursor.strftime("%Y-%m-%d"),
                    "timeStr": f"{cursor:%I:%M %p} - {slot_end:%I:%M %p}",
                })
                cursor += timedelta(minutes=30)
        day += timedelta(days=1)
    return slots


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

GMAIL_SKILL_DIR = os.getenv("GMAIL_SKILL_PATH", "/root/.claude/skills/gmail-skill")


def compose_reply(req_info, slot):
    dt = slot["start"] if isinstance(slot["start"], datetime) else datetime.fromisoformat(slot["start"])
    day_name = dt.strftime("%A")
    date_fmt = dt.strftime("%B %d, %Y")
    return f"""Hello,

        Thanks for reaching out to book a consultation.

        Here is the proposed slot:

        Scheduled Date: {day_name}, {date_fmt}
        Scheduled Time: {slot['timeStr']}
        Session Length: {req_info['durationHours']} hour(s)

        Please reply if you need to reschedule or have any questions.

        Kind regards,
        SkillsBench Scheduler"""


def dispatch_email(recipient, subj, body):
    cmd = ["node", "scripts/gmail-send.js", "--to", recipient, "--subject", subj, "--body", body]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=GMAIL_SKILL_DIR)
    payload = json.loads(proc.stdout)
    if not payload.get("success"):
        raise RuntimeError(f"Send failed: {payload}")
    return payload.get("messageId")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run():
    hf_token = os.getenv("HUGGINGFACE_API_TOKEN")
    if not hf_token:
        print("ERROR: HUGGINGFACE_API_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    model_id = os.getenv("LLM_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
    client = InferenceClient(token=hf_token)

    with open("/root/test_input.json") as fh:
        requests = json.load(fh)

    sent_ids = []
    for idx, item in enumerate(requests):
        print(f"\n=== Request {idx + 1}/{len(requests)} ===")
        body_text = item.get("email_text", "")
        sender = item.get("from_email", "")

        # 1. Parse
        print("  Parsing request...")
        info = extract_request_info(client, model_id, body_text, sender)
        print(f"  Duration={info['durationHours']}h  Window={info['windowStart']}-{info['windowEnd']}")
        print(f"  Dates={info['firstDate']} to {info['lastDate']}")

        # 2. Find slots
        print("  Checking calendar...")
        open_slots = compute_open_slots(info)
        print(f"  {len(open_slots)} open slot(s) found")
        if not open_slots:
            print("  WARNING: no slots available!")
            continue

        chosen = open_slots[0]
        print(f"  Chosen: {chosen['date']} {chosen['timeStr']}")

        # 3. Send reply
        print("  Sending confirmation...")
        reply_body = compose_reply(info, chosen)
        dt = chosen["start"] if isinstance(chosen["start"], datetime) else datetime.fromisoformat(chosen["start"])
        subject_line = f"Consultation Confirmed - {dt:%A, %B %d} at {chosen['timeStr'].split(' - ')[0]}"
        mid = dispatch_email(sender, subject_line, reply_body)
        print(f"  Sent! messageId={mid}")
        sent_ids.append({"messageId": mid})

    # 4. Write results
    output_path = os.getenv("OUTPUT_FILE", "/root/results.json")
    output = {
        "sent_results": sent_ids,
        "summary": {"total": len(requests), "emails_sent": len(sent_ids)},
    }
    with open(output_path, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\nResults written to {output_path}")


if __name__ == "__main__":
    run()
PYEOF
