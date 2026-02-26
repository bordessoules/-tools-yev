"""
Geekadomicile Email Parser POC
Parses incoming call notifications, repair notes, and payment receipts
into structured repair tickets, grouped by client.
"""

import imaplib
import email
import json
import re
import os
from datetime import datetime
from email.header import decode_header
from urllib.parse import unquote
from dataclasses import dataclass, field
from typing import Optional
from fetch_emails import connect_imap, decode_mime_header, get_email_body


# ─── Client Registry ───────────────────────────────────────────

CLIENTS_FILE = os.path.join(os.path.dirname(__file__), "clients.json")


@dataclass
class Client:
    id: str
    name: str
    phones: list
    emails: list
    address: str = ""
    notes: str = ""


def load_clients() -> list:
    """Load client registry from JSON file."""
    if not os.path.exists(CLIENTS_FILE):
        return []
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Client(**c) for c in data.get("clients", [])]


def build_phone_index(clients: list) -> dict:
    """Build a phone number -> client lookup."""
    index = {}
    for client in clients:
        for phone in client.phones:
            # Normalize: store with and without country code
            index[phone] = client
            # Also index without +33 prefix (as 0...)
            if phone.startswith("+33"):
                index["0" + phone[3:]] = client
    return index


def build_email_index(clients: list) -> dict:
    """Build an email address -> client lookup."""
    index = {}
    for client in clients:
        for addr in client.emails:
            index[addr.lower()] = client
    return index


# ─── Data Models ────────────────────────────────────────────────

@dataclass
class CallRecord:
    call_sid: str
    caller_number: str
    called_number: str
    forwarded_from: Optional[str]
    country: str
    direction: str
    call_status: str
    date: str
    timestamp: Optional[datetime] = None
    stir_verstat: str = ""


@dataclass
class RepairNote:
    text: str
    date: str
    author: str
    timestamp: Optional[datetime] = None


@dataclass
class PaymentRecord:
    amount: Optional[str]
    date: str
    card_last4: Optional[str]
    reference: Optional[str]
    bank: Optional[str]
    subscription_info: Optional[str] = None


@dataclass
class CustomerEmail:
    sender: str
    subject: str
    date: str
    body_preview: str


@dataclass
class RepairTicket:
    """A repair ticket combining call info and notes."""
    call: CallRecord
    notes: list = field(default_factory=list)
    payment: Optional[PaymentRecord] = None

    def display(self, indent="  "):
        print(f"{indent}Call: {self.call.date}")
        print(f"{indent}  From: {self.call.caller_number}", end="")
        if self.call.forwarded_from:
            print(f" (via {self.call.forwarded_from})", end="")
        print()
        print(f"{indent}  SID:  {self.call.call_sid[:16]}...")
        if self.notes:
            for note in self.notes:
                print(f"{indent}  Note [{note.date}]:")
                for line in note.text.strip().split("\n"):
                    print(f"{indent}    > {line.strip()}")
        else:
            print(f"{indent}  (no notes)")


@dataclass
class ClientReport:
    """All activity for one client."""
    client: Optional[Client]
    tickets: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    payments: list = field(default_factory=list)

    def display(self):
        if self.client:
            label = f"{self.client.name} [{self.client.id}]"
            phones = ", ".join(self.client.phones)
        else:
            label = "UNKNOWN CLIENT"
            phones = "?"

        print(f"\n{'='*60}")
        print(f"  CLIENT: {label}")
        print(f"  Phones: {phones}")
        if self.client and self.client.address:
            print(f"  Address: {self.client.address}")
        print(f"  Tickets: {len(self.tickets)} | Emails: {len(self.emails)} | Payments: {len(self.payments)}")
        print(f"{'='*60}")

        if self.tickets:
            print(f"\n  -- Repair Tickets --")
            for i, ticket in enumerate(self.tickets, 1):
                print(f"\n  [{i}]")
                ticket.display(indent="    ")

        if self.emails:
            print(f"\n  -- Direct Emails --")
            for em in self.emails:
                print(f"\n    {em.date}")
                print(f"    Subject: {em.subject}")
                print(f"    Preview: {em.body_preview[:100]}...")

        if self.payments:
            print(f"\n  -- Payments --")
            for p in self.payments:
                print(f"\n    {p.date}: {p.amount} EUR (****{p.card_last4})")
                if p.subscription_info:
                    print(f"    {p.subscription_info}")


# ─── Parsers ────────────────────────────────────────────────────

def parse_twilio_json(body: str) -> Optional[dict]:
    """Extract and parse Twilio JSON from an email body."""
    match = re.search(r'\{["\']Called["\'].*?\}', body, re.DOTALL)
    if not match:
        return None

    json_str = match.group(0)
    json_str = re.sub(r'"CallToken":"[^"]*"', '"CallToken":""', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            return json.loads(unquote(json_str))
        except json.JSONDecodeError:
            return None


def parse_call_email(msg, body: str) -> Optional[CallRecord]:
    """Parse an incoming call notification email."""
    twilio_data = parse_twilio_json(body)
    if not twilio_data:
        return None

    return CallRecord(
        call_sid=twilio_data.get("CallSid", ""),
        caller_number=twilio_data.get("From", twilio_data.get("Caller", "")),
        called_number=twilio_data.get("To", twilio_data.get("Called", "")),
        forwarded_from=twilio_data.get("ForwardedFrom") or twilio_data.get("CalledVia") or None,
        country=twilio_data.get("CallerCountry", ""),
        direction=twilio_data.get("Direction", ""),
        call_status=twilio_data.get("CallStatus", ""),
        date=msg["Date"] or "",
        stir_verstat=twilio_data.get("StirVerstat", ""),
    )


def extract_reply_note(body: str, msg) -> Optional[RepairNote]:
    """Extract the user's note from a reply email."""
    separators = [
        r'\n\s*On \d+/\d+/\d+',
        r'\n\s*\d+ \w+\. \d{4}',
        r'\n\s*\d+ \w+ \d{4}',
        r'\n--\s*\n',
        r'\n-- \n',
    ]

    note_text = body
    for sep in separators:
        match = re.search(sep, body)
        if match:
            candidate = body[:match.start()].strip()
            if candidate and len(candidate) < len(note_text):
                note_text = candidate

    note_text = note_text.strip()
    if not note_text or note_text == body.strip():
        return None
    if len(note_text) > 500:
        return None

    author = decode_mime_header(msg["From"])
    author_match = re.match(r'^(.*?)\s*<', author)
    if author_match:
        author = author_match.group(1).strip()

    return RepairNote(
        text=note_text,
        date=msg["Date"] or "",
        author=author,
    )


def parse_payment_email(body: str) -> Optional[PaymentRecord]:
    """Parse a payment notification email."""
    if "PAIEMENT ACCEPT" not in body.upper():
        return None

    card_match = re.search(r'-{4,}(\d{4})', body)
    last4 = card_match.group(1) if card_match else None

    date_match = re.search(r'Le (\d{2}/\d{2}/\d{4})', body)
    date_str = date_match.group(1) if date_match else ""

    ref_match = re.search(r'\n(\d{7})\n', body)
    reference = ref_match.group(1) if ref_match else None

    bank_match = re.search(r'(CREDIT \w+\s+\w+)', body)
    bank = bank_match.group(1).strip() if bank_match else None

    sub_match = re.search(r'Prochain.*?(\d+\.\d+ EUR)', body)
    sub_info = sub_match.group(0) if sub_match else None

    amount_match = re.search(r'(\d+[\.,]\d{2})\s*EUR', body)
    amount = amount_match.group(1) if amount_match else None

    return PaymentRecord(
        amount=amount,
        date=date_str,
        card_last4=last4,
        reference=reference,
        bank=bank,
        subscription_info=sub_info,
    )


# ─── Client Matching ───────────────────────────────────────────

def find_client_for_phone(phone: str, phone_index: dict) -> Optional[Client]:
    """Look up client by phone number."""
    return phone_index.get(phone)


def find_client_for_email(sender: str, email_index: dict) -> Optional[Client]:
    """Look up client by email address."""
    # Extract email from "Name <email>" format
    match = re.search(r'<([^>]+)>', sender)
    addr = match.group(1).lower() if match else sender.lower()
    return email_index.get(addr)


# ─── Main Processing ───────────────────────────────────────────

def process_all_emails():
    """Fetch and process all emails, grouped by client."""
    # Load client registry
    clients = load_clients()
    phone_index = build_phone_index(clients)
    email_index = build_email_index(clients)
    print(f"Loaded {len(clients)} client(s) from registry.")

    mail = connect_imap()

    calls = {}        # call_sid -> CallRecord
    notes = []        # list of (call_sid, RepairNote)
    payments = []     # list of PaymentRecord
    customer_emails = []  # list of CustomerEmail

    folders = ["INBOX", "Sent", "Archive.2025", "Archive.2026", "Archives.2026"]

    for folder in folders:
        try:
            status, _ = mail.select(folder, readonly=True)
            if status != "OK":
                continue

            status, messages = mail.search(None, "ALL")
            if status != "OK":
                continue

            msg_ids = messages[0].split()
            print(f"Processing {folder}: {len(msg_ids)} emails...")

            for msg_id in msg_ids:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                body = get_email_body(msg)
                sender = decode_mime_header(msg["From"])
                subject = decode_mime_header(msg["Subject"])

                # 1. Payment emails
                if "e-transactions" in sender.lower() or "ticket paiement" in subject.lower():
                    payment = parse_payment_email(body)
                    if payment:
                        payments.append(payment)
                        continue

                # 2. Original call notifications (from incall@)
                if "incall@" in sender.lower() and "Appel entrant" in subject:
                    call = parse_call_email(msg, body)
                    if call and call.call_sid:
                        calls[call.call_sid] = call
                        continue

                # 3. Replies with notes (Re: Appel entrant)
                if subject.startswith("Re:") and "Appel entrant" in subject:
                    note = extract_reply_note(body, msg)
                    twilio_data = parse_twilio_json(body)
                    if twilio_data:
                        call_sid = twilio_data.get("CallSid", "")
                        if note:
                            notes.append((call_sid, note))
                        if call_sid and call_sid not in calls:
                            call = parse_call_email(msg, body)
                            if call:
                                calls[call.call_sid] = call
                        continue

                # 4. Other customer emails
                if "geekadomicile" not in sender.lower() and "incall@" not in sender.lower():
                    customer_emails.append(CustomerEmail(
                        sender=sender,
                        subject=subject,
                        date=msg["Date"] or "",
                        body_preview=body[:200],
                    ))

        except Exception as e:
            print(f"  Error processing {folder}: {e}")

    mail.logout()

    # ─── Build Tickets (with dedup) ───
    tickets = {}
    for call_sid, call in calls.items():
        tickets[call_sid] = RepairTicket(call=call)

    for call_sid, note in notes:
        if call_sid in tickets:
            existing_texts = {n.text.strip() for n in tickets[call_sid].notes}
            if note.text.strip() not in existing_texts:
                tickets[call_sid].notes.append(note)

    # ─── Group by Client ───
    # client_id -> ClientReport
    reports = {}
    unknown_report = ClientReport(client=None)

    for call_sid, ticket in tickets.items():
        client = find_client_for_phone(ticket.call.caller_number, phone_index)
        if client:
            if client.id not in reports:
                reports[client.id] = ClientReport(client=client)
            reports[client.id].tickets.append(ticket)
        else:
            unknown_report.tickets.append(ticket)

    for ce in customer_emails:
        client = find_client_for_email(ce.sender, email_index)
        if client:
            if client.id not in reports:
                reports[client.id] = ClientReport(client=client)
            reports[client.id].emails.append(ce)
        else:
            unknown_report.emails.append(ce)

    # Payments are from your own account (e-transactions), not client-specific
    # but we keep them in the summary

    # ─── Display ───
    print(f"\n{'#'*60}")
    print(f"  GEEKADOMICILE - CLIENT REPORT")
    print(f"{'#'*60}")
    print(f"\n  Total calls:    {len(calls)}")
    print(f"  Total notes:    {sum(len(t.notes) for t in tickets.values())}")
    print(f"  Total payments: {len(payments)}")
    print(f"  Customer emails: {len(customer_emails)}")
    print(f"  Known clients:  {len(reports)}")
    if unknown_report.tickets or unknown_report.emails:
        print(f"  Unknown:        {len(unknown_report.tickets)} tickets, {len(unknown_report.emails)} emails")

    # Display known clients
    for report in sorted(reports.values(), key=lambda r: r.client.name):
        # Sort tickets by date
        report.tickets.sort(key=lambda t: t.call.date)
        report.display()

    # Display unknown
    if unknown_report.tickets or unknown_report.emails:
        unknown_report.display()

    # Display payments separately
    if payments:
        print(f"\n{'='*60}")
        print(f"  PAYMENTS (shop account)")
        print(f"{'='*60}")
        for p in payments:
            print(f"\n  {p.date}: {p.amount} EUR (****{p.card_last4})")
            if p.subscription_info:
                print(f"  {p.subscription_info}")

    return reports, unknown_report, payments


if __name__ == "__main__":
    process_all_emails()
