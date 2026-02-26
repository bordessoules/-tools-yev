"""
TimeCop time tracking connector.
Parses timecop.csv export and filters entries by client name.
"""

import csv
import os
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


TIMECOP_FILE = os.path.join(os.path.dirname(__file__), "..", "timecop.csv")


@dataclass
class TimeCopEntry:
    date: str
    project: str
    description: str
    start: Optional[datetime]
    end: Optional[datetime]
    duration_hours: float
    notes: str

    @property
    def duration_display(self):
        """Format duration as 'Xh Ymin'."""
        total_min = round(self.duration_hours * 60)
        h = total_min // 60
        m = total_min % 60
        if h > 0 and m > 0:
            return f"{h}h{m:02d}min"
        elif h > 0:
            return f"{h}h00"
        else:
            return f"{m}min"


def _strip_accents(text):
    """Remove accents for fuzzy matching: Danièle → Daniele."""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_iso(dt_str):
    """Parse ISO 8601 datetime string to Python datetime."""
    if not dt_str:
        return None
    try:
        # Handle "2024-02-20T12:42:39.396Z" format
        dt_str = dt_str.rstrip("Z")
        if "." in dt_str:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f")
        else:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def load_timecop_entries():
    """Load all entries from timecop.csv."""
    entries = []
    filepath = os.path.abspath(TIMECOP_FILE)
    if not os.path.exists(filepath):
        print(f"  TimeCop file not found: {filepath}")
        return entries

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                duration = float(row.get("Temps (heures)", 0) or 0)
            except (ValueError, TypeError):
                duration = 0.0

            entry = TimeCopEntry(
                date=row.get("Date", ""),
                project=row.get("Projet", "").strip(),
                description=row.get("La description", "").strip(),
                start=_parse_iso(row.get("Heure de début", "")),
                end=_parse_iso(row.get("Heure de fin", "")),
                duration_hours=duration,
                notes=row.get("Remarques", "").strip(),
            )
            entries.append(entry)

    return entries


def fetch_timecop_for_client(client):
    """Fetch TimeCop entries matching a client by name (accent-insensitive).

    Match logic: at least 2 name parts must appear in the description,
    or all parts if the name has ≤2 parts.
    """
    all_entries = load_timecop_entries()
    matched = []

    name = client.get("name", "")
    name_parts = [_strip_accents(p).lower() for p in name.split() if len(p) > 2]
    if not name_parts:
        return matched

    min_match = min(2, len(name_parts))

    for entry in all_entries:
        desc_norm = _strip_accents(entry.description).lower()
        hits = sum(1 for p in name_parts if p in desc_norm)
        if hits >= min_match:
            matched.append(entry)

    matched.sort(key=lambda e: e.start or datetime.min)
    return matched


if __name__ == "__main__":
    entries = load_timecop_entries()
    print(f"Total TimeCop entries: {len(entries)}")
    print(f"Date range: {entries[0].date} - {entries[-1].date}")

    # Test with Duhammel
    client = {"name": "Daniele Duhammel"}
    matched = fetch_timecop_for_client(client)
    print(f"\nEntries for Duhammel: {len(matched)}")
    total_hours = sum(e.duration_hours for e in matched)
    print(f"Total time: {total_hours:.1f}h")
    for e in matched:
        print(f"  {e.date} | {e.description} | {e.duration_display} | {e.start}")
