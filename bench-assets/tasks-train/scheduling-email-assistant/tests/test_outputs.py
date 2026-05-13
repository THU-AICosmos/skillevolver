"""
Use this file to define pytest tests that verify the outputs of the task.

This file will be copied to /tests/test_outputs.py and run by the /tests/test.sh file
from the working directory.
"""

import json
import os
import re
import subprocess
import time

# Expected values for the 4 consultation booking replies
EXPECTED_DATES = [
    "Tuesday, February 10, 2026",
    "Wednesday, February 11, 2026",
    "Monday, February 09, 2026",
    "Thursday, February 12, 2026",
]
EXPECTED_TIMES = [
    "02:00 PM - 02:30 PM",
    "09:00 AM - 11:00 AM",
    "10:00 AM - 11:00 AM",
    "03:00 PM - 03:45 PM",
]

EXPECTED_RECIPIENTS = [
    "maria.garcia@example.designs.org",
    "d.chen@example.techpartners.io",
    "sophia.patel@example.creativeworks.net",
    "j.okafor@example.finance-group.com",
]


def locate_gmail_skill():
    """Locate the gmail skill directory."""
    return os.getenv("GMAIL_SKILL_PATH", "/root/.claude/skills/gmail-skill")


def fetch_email_content(msg_id, retries=3, wait_sec=2):
    """Retrieve email content by message ID via gmail-read.js with retry."""
    skill_dir = locate_gmail_skill()
    cmd = ["node", "scripts/gmail-read.js", "--id", msg_id]

    err = None
    for attempt in range(retries):
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=skill_dir)
        if proc.returncode == 0:
            payload = json.loads(proc.stdout)
            if payload.get("success"):
                return payload
            err = payload.get("error", "Unknown error")
        else:
            err = proc.stderr

        if attempt < retries - 1:
            time.sleep(wait_sec)

    raise Exception(f"Could not read email {msg_id} after {retries} tries: {err}")


def load_output_results():
    """Load sent_results from results.json."""
    path = os.getenv("RESULTS_PATH", "/root/results.json")
    with open(path) as fh:
        return json.load(fh)


def parse_time_field(body_text):
    """Extract the Scheduled Time value from the email body."""
    pat = r"Scheduled Time:\s*(\d{1,2}:\d{2}\s*[AP]M\s*-\s*\d{1,2}:\d{2}\s*[AP]M)"
    m = re.search(pat, body_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def parse_date_field(body_text):
    """Extract the Scheduled Date value from the email body."""
    pat = r"Scheduled Date:\s*(\w+,\s*\w+\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})"
    m = re.search(pat, body_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def normalize_date_str(raw):
    """Normalize date string for flexible comparison."""
    s = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", raw)
    s = re.sub(r"(\d+)\s+(\d{4})", r"\1, \2", s)
    s = re.sub(r"(\w+)\s+(\d),", r"\1 0\2,", s)
    return s


def test_consultation_replies():
    """Verify that all 4 consultation replies have the correct date and time."""
    data = load_output_results()["sent_results"]

    assert len(data) == 4, f"Expected 4 sent messages, got {len(data)}"

    for entry, exp_date, exp_time in zip(data, EXPECTED_DATES, EXPECTED_TIMES):
        mid = entry["messageId"]
        email = fetch_email_content(mid)

        assert email.get("success"), f"Failed to fetch email {mid}"

        body = email.get("body", "")
        print(body)

        actual_date = parse_date_field(body)
        actual_time = parse_time_field(body)

        assert actual_date is not None, f"No Scheduled Date found in email {mid}"
        assert actual_time is not None, f"No Scheduled Time found in email {mid}"

        norm_exp_time = " ".join(exp_time.split())
        norm_act_time = " ".join(actual_time.split())
        assert norm_exp_time == norm_act_time, (
            f"Time mismatch for {mid}:\n"
            f"  Expected: {norm_exp_time}\n"
            f"  Actual:   {norm_act_time}\n"
            f"  Body:\n{body}"
        )

        norm_exp_date = normalize_date_str(exp_date)
        norm_act_date = normalize_date_str(actual_date)
        assert norm_exp_date == norm_act_date, (
            f"Date mismatch for {mid}:\n"
            f"  Expected: {exp_date} (norm: {norm_exp_date})\n"
            f"  Actual:   {actual_date} (norm: {norm_act_date})\n"
            f"  Body:\n{body}"
        )
        print(f"OK email {mid} => {actual_date}, {norm_act_time}")


def test_consultation_recipients():
    """Verify that each reply was sent to the correct recipient."""
    data = load_output_results()["sent_results"]

    for entry, exp_to in zip(data, EXPECTED_RECIPIENTS):
        mid = entry["messageId"]
        email = fetch_email_content(mid)

        assert email.get("success"), f"Failed to fetch email {mid}"

        actual_to = email.get("to", "")
        assert exp_to in actual_to, (
            f"Recipient mismatch for {mid}:\n"
            f"  Expected: {exp_to}\n"
            f"  Actual:   {actual_to}"
        )
        print(f"OK email {mid} recipient => {exp_to}")
