"""
Nextcloud CardDAV/CalDAV/WebDAV connector.
Connects to mail.geekadomicile.com/cloud to sync contacts and calendars.

Uses the same credentials as the mail server.

Endpoints discovered:
- CardDAV: /cloud/remote.php/dav/addressbooks/users/{user}/contacts/
- CalDAV:  /cloud/remote.php/dav/calendars/users/{user}/personal/
- WebDAV:  /cloud/remote.php/dav/files/{user}/
"""

import re
import unicodedata
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

# ── Config ──
CLOUD_BASE = "https://mail.geekadomicile.com/cloud"
DAV_BASE = f"{CLOUD_BASE}/remote.php/dav"
CLOUD_USER = "ykassine-test@geekadomicile.com"
CLOUD_PASS = "JHygR4P8"

# XML namespaces
NS = {
    "d": "DAV:",
    "card": "urn:ietf:params:xml:ns:carddav",
    "cal": "urn:ietf:params:xml:ns:caldav",
    "oc": "http://owncloud.org/ns",
    "nc": "http://nextcloud.org/ns",
}


@dataclass
class Contact:
    uid: str
    full_name: str
    phones: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    address: str = ""
    notes: str = ""
    vcf_url: str = ""
    raw_vcard: str = ""

    @property
    def display(self):
        parts = [self.full_name]
        if self.phones:
            parts.append(f"Tel: {', '.join(self.phones)}")
        if self.emails:
            parts.append(f"Email: {', '.join(self.emails)}")
        if self.address:
            parts.append(f"Addr: {self.address}")
        return " | ".join(parts)


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    dtstart: str
    dtend: str = ""
    location: str = ""
    description: str = ""
    raw_ical: str = ""


def _auth():
    return (CLOUD_USER, CLOUD_PASS)


def _dav_request(method, url, body=None, headers=None):
    """Make a DAV request with auth."""
    hdrs = {"Content-Type": "application/xml; charset=utf-8"}
    if headers:
        hdrs.update(headers)
    resp = requests.request(method, url, auth=_auth(), headers=hdrs,
                            data=body, timeout=30)
    resp.raise_for_status()
    return resp


def _parse_vcard(vcard_text):
    """Parse a vCard text into a Contact object."""
    uid = ""
    fn = ""
    phones = []
    emails = []
    address = ""
    notes = ""

    for line in vcard_text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line or line.startswith("BEGIN:") or line.startswith("END:"):
            continue

        # UID
        if line.upper().startswith("UID:"):
            uid = line.split(":", 1)[1].strip()

        # Full name
        elif line.upper().startswith("FN:"):
            fn = line.split(":", 1)[1].strip()

        # Phone numbers (handle Nextcloud prefixed properties)
        elif "TEL" in line.upper() and ":" in line:
            phone = line.split(":", 1)[1].strip()
            # Normalize phone: remove spaces
            phone_clean = re.sub(r'\s+', '', phone)
            if phone_clean and phone_clean not in phones:
                phones.append(phone_clean)

        # Email (handle Nextcloud prefixed properties)
        elif "EMAIL" in line.upper() and ":" in line and "@" in line:
            email_val = line.split(":", 1)[1].strip()
            if email_val and email_val not in emails:
                emails.append(email_val)

        # Address
        elif line.upper().startswith("ADR") and ":" in line:
            parts = line.split(":", 1)[1].split(";")
            # ADR format: PO;ext;street;city;state;zip;country
            addr_parts = [p.strip() for p in parts if p.strip()]
            address = " ".join(addr_parts)

        # Notes
        elif line.upper().startswith("NOTE:"):
            notes = line.split(":", 1)[1].strip()
            # Decode escaped newlines
            notes = notes.replace("\\n", "\n")

    return Contact(
        uid=uid, full_name=fn, phones=phones, emails=emails,
        address=address, notes=notes, raw_vcard=vcard_text,
    )


def _parse_ical_event(ical_text):
    """Parse an iCalendar VEVENT into a CalendarEvent."""
    uid = ""
    summary = ""
    dtstart = ""
    dtend = ""
    location = ""
    description = ""

    in_event = False
    for line in ical_text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
        elif line == "END:VEVENT":
            in_event = False
        elif in_event:
            if line.upper().startswith("UID:"):
                uid = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif "DTSTART" in line.upper() and ":" in line:
                dtstart = line.split(":", 1)[1].strip()
            elif "DTEND" in line.upper() and ":" in line:
                dtend = line.split(":", 1)[1].strip()
            elif line.upper().startswith("LOCATION:"):
                location = line.split(":", 1)[1].strip()
            elif line.upper().startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip()
                description = description.replace("\\n", "\n")

    return CalendarEvent(
        uid=uid, summary=summary, dtstart=dtstart, dtend=dtend,
        location=location, description=description, raw_ical=ical_text,
    )


# ════════════════════════════════════════════════════════════════
# CARDDAV — Contacts
# ════════════════════════════════════════════════════════════════

def fetch_contacts(addressbook="contacts"):
    """Fetch all contacts from a CardDAV address book."""
    url = f"{DAV_BASE}/addressbooks/users/{CLOUD_USER}/{addressbook}/"
    body = """<?xml version="1.0"?>
    <card:addressbook-query xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
        <d:prop>
            <d:getetag/>
            <card:address-data/>
        </d:prop>
    </card:addressbook-query>"""

    resp = _dav_request("REPORT", url, body, {"Depth": "1"})
    root = ET.fromstring(resp.text)

    contacts = []
    for response in root.findall("d:response", NS):
        href = response.find("d:href", NS)
        addr_data = response.find(".//card:address-data", NS)
        if addr_data is not None and addr_data.text:
            vcard_text = addr_data.text.replace("\r\n", "\n")
            contact = _parse_vcard(vcard_text)
            if href is not None:
                contact.vcf_url = href.text
            contacts.append(contact)

    return contacts


def create_contact(contact, addressbook="contacts"):
    """Create a new contact via CardDAV PUT."""
    import uuid
    uid = contact.uid or str(uuid.uuid4())
    vcf_name = f"{uid}.vcf"
    url = f"{DAV_BASE}/addressbooks/users/{CLOUD_USER}/{addressbook}/{vcf_name}"

    # Build vCard
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"UID:{uid}",
        f"FN:{contact.full_name}",
    ]
    for i, phone in enumerate(contact.phones):
        if i == 0:
            lines.append(f"TEL;TYPE=CELL:{phone}")
        else:
            lines.append(f"TEL;TYPE=CELL:{phone}")
    for email_addr in contact.emails:
        lines.append(f"EMAIL;TYPE=HOME:{email_addr}")
    if contact.address:
        lines.append(f"ADR;TYPE=HOME:;;{contact.address};;;;")
    if contact.notes:
        escaped_notes = contact.notes.replace("\n", "\\n")
        lines.append(f"NOTE:{escaped_notes}")
    lines.append("END:VCARD")

    vcard = "\r\n".join(lines) + "\r\n"

    resp = requests.put(url, auth=_auth(),
                        headers={"Content-Type": "text/vcard; charset=utf-8"},
                        data=vcard.encode("utf-8"), timeout=30)
    resp.raise_for_status()
    return uid


def update_contact(contact, addressbook="contacts"):
    """Update an existing contact via CardDAV PUT (overwrites)."""
    if not contact.vcf_url:
        raise ValueError("Contact has no vcf_url — cannot update")

    url = f"https://mail.geekadomicile.com{contact.vcf_url}"

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"UID:{contact.uid}",
        f"FN:{contact.full_name}",
    ]
    for phone in contact.phones:
        lines.append(f"TEL;TYPE=CELL:{phone}")
    for email_addr in contact.emails:
        lines.append(f"EMAIL;TYPE=HOME:{email_addr}")
    if contact.address:
        lines.append(f"ADR;TYPE=HOME:;;{contact.address};;;;")
    if contact.notes:
        escaped_notes = contact.notes.replace("\n", "\\n")
        lines.append(f"NOTE:{escaped_notes}")
    lines.append("END:VCARD")

    vcard = "\r\n".join(lines) + "\r\n"

    resp = requests.put(url, auth=_auth(),
                        headers={"Content-Type": "text/vcard; charset=utf-8"},
                        data=vcard.encode("utf-8"), timeout=30)
    resp.raise_for_status()
    return True


def delete_contact(vcf_url):
    """Delete a contact by its vcf URL."""
    url = f"https://mail.geekadomicile.com{vcf_url}"
    resp = requests.delete(url, auth=_auth(), timeout=30)
    resp.raise_for_status()
    return True


# ════════════════════════════════════════════════════════════════
# CALDAV — Calendar
# ════════════════════════════════════════════════════════════════

def fetch_calendar_events(calendar="personal"):
    """Fetch all events from a CalDAV calendar."""
    url = f"{DAV_BASE}/calendars/{CLOUD_USER}/{calendar}/"
    body = """<?xml version="1.0"?>
    <cal:calendar-query xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
        <d:prop>
            <d:getetag/>
            <cal:calendar-data/>
        </d:prop>
        <cal:filter>
            <cal:comp-filter name="VCALENDAR">
                <cal:comp-filter name="VEVENT"/>
            </cal:comp-filter>
        </cal:filter>
    </cal:calendar-query>"""

    resp = _dav_request("REPORT", url, body, {"Depth": "1"})
    root = ET.fromstring(resp.text)

    events = []
    for response in root.findall("d:response", NS):
        cal_data = response.find(".//cal:calendar-data", NS)
        if cal_data is not None and cal_data.text:
            event = _parse_ical_event(cal_data.text)
            if event.summary:
                events.append(event)

    return events


def _strip_accents(text):
    """Remove accents for fuzzy matching: Danièle → Daniele."""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def parse_ical_datetime(dt_str):
    """Parse iCal datetime string to Python datetime.

    Formats: 20260212T090000, 20260212T090000Z, 20260212
    """
    if not dt_str:
        return None
    dt_str = dt_str.rstrip("Z")  # treat UTC same as local for display
    try:
        if "T" in dt_str:
            return datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
        else:
            return datetime.strptime(dt_str, "%Y%m%d")
    except ValueError:
        return None


def fetch_calendar_events_for_client(client, calendar="personal"):
    """Fetch calendar events filtered for a specific client.

    Matches by:
    - Client name parts (accent-insensitive)
    - Client address
    - Client email addresses
    """
    events = fetch_calendar_events(calendar)
    matched = []

    # Build match terms from client data
    name = client.get("name", "")
    name_parts = [_strip_accents(p).lower() for p in name.split() if len(p) > 2]
    address = client.get("address", "")
    # Extract street name for matching (e.g. "Jean De La Bruyère" from full address)
    addr_words = [_strip_accents(w).lower() for w in address.split()
                  if len(w) > 3 and not w.isdigit()]
    emails_lower = [e.lower() for e in client.get("emails", [])]

    for event in events:
        searchable = _strip_accents(
            f"{event.summary} {event.location} {event.description}"
        ).lower()

        # Match by name: at least 2 name parts present (or all if name has <=2 parts)
        min_match = min(2, len(name_parts))
        name_hits = sum(1 for p in name_parts if p in searchable)
        if name_hits >= min_match and name_parts:
            event.parsed_date = parse_ical_datetime(event.dtstart)
            matched.append(event)
            continue

        # Match by address: check for distinctive street words
        # Need at least 3 address words matching (to avoid false positives)
        if addr_words:
            addr_hits = sum(1 for w in addr_words if w in searchable)
            if addr_hits >= 3:
                event.parsed_date = parse_ical_datetime(event.dtstart)
                matched.append(event)
                continue

        # Match by email
        for em in emails_lower:
            if em in searchable:
                event.parsed_date = parse_ical_datetime(event.dtstart)
                matched.append(event)
                break

    # Sort by date
    matched.sort(key=lambda e: e.parsed_date or datetime.min)
    return matched


# ════════════════════════════════════════════════════════════════
# WEBDAV — Files
# ════════════════════════════════════════════════════════════════

def list_files(path="/"):
    """List files/folders via WebDAV."""
    url = f"{DAV_BASE}/files/{CLOUD_USER}{path}"
    body = """<?xml version="1.0"?>
    <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
        <d:prop>
            <d:displayname/>
            <d:getcontentlength/>
            <d:getcontenttype/>
            <d:getlastmodified/>
            <d:resourcetype/>
        </d:prop>
    </d:propfind>"""

    resp = _dav_request("PROPFIND", url, body, {"Depth": "1"})
    root = ET.fromstring(resp.text)

    files = []
    for response in root.findall("d:response", NS):
        href = response.find("d:href", NS)
        displayname = response.find(".//d:displayname", NS)
        content_type = response.find(".//d:getcontenttype", NS)
        content_length = response.find(".//d:getcontentlength", NS)
        resource_type = response.find(".//d:resourcetype", NS)
        last_modified = response.find(".//d:getlastmodified", NS)

        is_dir = resource_type is not None and resource_type.find("d:collection", NS) is not None

        files.append({
            "href": href.text if href is not None else "",
            "name": displayname.text if displayname is not None else "",
            "type": "folder" if is_dir else (content_type.text if content_type is not None else ""),
            "size": int(content_length.text) if content_length is not None and content_length.text else 0,
            "modified": last_modified.text if last_modified is not None else "",
        })

    return files


# ════════════════════════════════════════════════════════════════
# Sync contacts → clients.json
# ════════════════════════════════════════════════════════════════

def sync_contacts_to_clients_json():
    """Fetch contacts from CardDAV and update clients.json."""
    import json
    import os

    contacts = fetch_contacts()
    clients_file = os.path.join(os.path.dirname(__file__), "clients.json")

    # Load existing clients
    existing = {}
    if os.path.exists(clients_file):
        with open(clients_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for c in data.get("clients", []):
            existing[c["id"]] = c

    # Merge contacts into clients
    for contact in contacts:
        if not contact.full_name or contact.full_name.endswith("@geekadomicile.com"):
            continue

        # Generate client ID from name
        name_parts = contact.full_name.lower().split()
        if len(name_parts) >= 2:
            client_id = f"{name_parts[-1]}-{name_parts[0]}"
        else:
            client_id = name_parts[0]

        # Normalize phones: ensure +33 format
        phones = []
        for p in contact.phones:
            p_clean = re.sub(r'[\s\-\.]', '', p)
            if p_clean.startswith("0") and len(p_clean) == 10:
                p_clean = "+33" + p_clean[1:]
            phones.append(p_clean)

        client = existing.get(client_id, {
            "id": client_id,
            "name": contact.full_name,
            "phones": [],
            "emails": [],
            "address": "",
            "notes": "",
        })

        # Update from CardDAV (CardDAV is source of truth for contact info)
        client["name"] = contact.full_name
        # Merge phones (keep existing + add new)
        for p in phones:
            if p not in client["phones"]:
                client["phones"].append(p)
        # Merge emails
        for e in contact.emails:
            if e not in client["emails"]:
                client["emails"].append(e)
        if contact.address:
            client["address"] = contact.address
        if contact.notes:
            client["notes"] = contact.notes

        client["carddav_uid"] = contact.uid
        existing[client_id] = client

    # Save
    clients_data = {"clients": list(existing.values())}
    with open(clients_file, "w", encoding="utf-8") as f:
        json.dump(clients_data, f, indent=2, ensure_ascii=False)

    return list(existing.values())


# ════════════════════════════════════════════════════════════════
# Main — demo
# ════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("NEXTCLOUD CLOUD CONNECTOR")
    print(f"Server: {CLOUD_BASE}")
    print(f"User: {CLOUD_USER}")
    print("=" * 60)

    # ── Contacts ──
    print("\n--- CARDDAV CONTACTS ---")
    contacts = fetch_contacts()
    print(f"Found {len(contacts)} contacts in 'Contacts' address book:")
    for c in contacts:
        print(f"  {c.display}")
        if c.notes:
            for line in c.notes.split("\n"):
                print(f"    Note: {line}")

    # Recently contacted
    recent = fetch_contacts("z-app-generated--contactsinteraction--recent")
    print(f"\nFound {len(recent)} in 'Recently contacted':")
    for c in recent:
        print(f"  {c.full_name} ({', '.join(c.emails) or ', '.join(c.phones) or '?'})")

    # ── Calendar ──
    print("\n--- CALDAV CALENDAR ---")
    events = fetch_calendar_events()
    print(f"Found {len(events)} events in 'Personal' calendar:")
    for e in events:
        print(f"  {e.dtstart} | {e.summary}")
        if e.location:
            print(f"    Location: {e.location}")

    # ── Files ──
    print("\n--- WEBDAV FILES ---")
    files = list_files("/")
    print(f"Root directory ({len(files)} items):")
    for f in files:
        size_str = f" ({f['size']} bytes)" if f['size'] else ""
        print(f"  {'[DIR]' if f['type'] == 'folder' else f['type']:20s} {f['name'] or '/'}{size_str}")

    # ── Sync to clients.json ──
    print("\n--- SYNC TO CLIENTS.JSON ---")
    clients = sync_contacts_to_clients_json()
    print(f"Synced {len(clients)} clients:")
    for c in clients:
        print(f"  {c['id']}: {c['name']} | Phones: {c['phones']} | Emails: {c['emails']}")


if __name__ == "__main__":
    main()
