"""
Phone call log connector.
Parses Android call log export (JSON) and filters entries by client phone numbers.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


CALLLOG_FILE = os.path.join(os.path.dirname(__file__), "..", "calls-2026-01-10.json")

# Android call log types
CALL_TYPE_INCOMING = 1
CALL_TYPE_OUTGOING = 2
CALL_TYPE_MISSED = 3


@dataclass
class CallLogEntry:
    number: str  # normalized phone number
    display_name: str
    duration_secs: int
    date: Optional[datetime]
    call_type: int  # 1=incoming, 2=outgoing, 3=missed
    location: str

    @property
    def duration_display(self):
        """Format duration as 'Xmin Ys' or 'Xh Ymin'."""
        if self.duration_secs == 0:
            return "0s"
        total_min = self.duration_secs // 60
        secs = self.duration_secs % 60
        if total_min >= 60:
            h = total_min // 60
            m = total_min % 60
            if m > 0:
                return f"{h}h{m:02d}min"
            return f"{h}h00"
        elif total_min > 0:
            if secs > 0:
                return f"{total_min}min{secs:02d}s"
            return f"{total_min}min"
        else:
            return f"{secs}s"

    @property
    def call_type_label(self):
        """Human-readable call type."""
        if self.call_type == CALL_TYPE_INCOMING:
            return "Appel entrant"
        elif self.call_type == CALL_TYPE_OUTGOING:
            return "Appel sortant"
        elif self.call_type == CALL_TYPE_MISSED:
            return "Appel manque"
        # type 4 = voicemail, type 5 = rejected, etc.
        return "Appel manque"

    @property
    def call_type_key(self):
        """Type key for timeline classification."""
        if self.call_type == CALL_TYPE_INCOMING:
            return "call_incoming"
        elif self.call_type == CALL_TYPE_OUTGOING:
            return "call_outgoing"
        elif self.call_type == CALL_TYPE_MISSED:
            return "call_missed"
        # Default: treat unknown types as missed
        return "call_missed"

    @property
    def direction(self):
        """Direction for timeline styling."""
        if self.call_type == CALL_TYPE_OUTGOING:
            return "out"
        return "in"


def _normalize_phone(number):
    """Normalize phone number for matching: strip spaces, ensure + prefix."""
    if not number:
        return ""
    num = re.sub(r'[\s\-\.]', '', number)
    # Convert French national to international
    if num.startswith("0") and len(num) == 10:
        num = "+33" + num[1:]
    return num


def load_call_log():
    """Load all entries from the call log JSON."""
    filepath = os.path.abspath(CALLLOG_FILE)
    if not os.path.exists(filepath):
        print(f"  Call log file not found: {filepath}")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    for record in data:
        try:
            duration = int(record.get("duration", 0) or 0)
        except (ValueError, TypeError):
            duration = 0

        try:
            epoch_ms = int(record.get("date", 0) or 0)
            dt = datetime.fromtimestamp(epoch_ms / 1000.0) if epoch_ms else None
        except (ValueError, TypeError, OSError):
            dt = None

        try:
            call_type = int(record.get("type", 1) or 1)
        except (ValueError, TypeError):
            call_type = 1

        number = _normalize_phone(
            record.get("normalized_number", "") or record.get("number", "")
        )

        entry = CallLogEntry(
            number=number,
            display_name=record.get("display_name", "") or record.get("name", "") or "",
            duration_secs=duration,
            date=dt,
            call_type=call_type,
            location=record.get("geocoded_location", ""),
        )
        entries.append(entry)

    return entries


def fetch_calls_for_client(client):
    """Fetch call log entries for a client by phone number matching."""
    all_entries = load_call_log()
    matched = []

    # Normalize client phone numbers
    client_phones = set()
    for phone in client.get("phones", []):
        norm = _normalize_phone(phone)
        if norm:
            client_phones.add(norm)

    if not client_phones:
        return matched

    for entry in all_entries:
        if entry.number in client_phones:
            matched.append(entry)

    matched.sort(key=lambda e: e.date or datetime.min)
    return matched


if __name__ == "__main__":
    entries = load_call_log()
    print(f"Total call log entries: {len(entries)}")

    if entries:
        dates = [e.date for e in entries if e.date]
        if dates:
            print(f"Date range: {min(dates).strftime('%Y-%m-%d')} - {max(dates).strftime('%Y-%m-%d')}")

    # Test with Duhammel
    client = {
        "name": "Daniele Duhammel",
        "phones": ["+33681372829", "+33139660499"],
    }
    matched = fetch_calls_for_client(client)
    print(f"\nCalls for Duhammel: {len(matched)}")

    type_counts = {}
    total_duration = 0
    for e in matched:
        label = e.call_type_label
        type_counts[label] = type_counts.get(label, 0) + 1
        total_duration += e.duration_secs
        print(f"  {e.date.strftime('%Y-%m-%d %H:%M') if e.date else '?'} | "
              f"{label} | {e.duration_display} | {e.number}")

    print(f"\nBy type: {type_counts}")
    print(f"Total call time: {total_duration // 60}min {total_duration % 60}s")
