"""
Email Fetcher POC - Computer Repair Shop
Connects to IMAP mailbox and fetches recent emails for analysis.
"""

import imaplib
import email
from email.header import decode_header
import os
from datetime import datetime


# --- Config (move to .env for production) ---
IMAP_SERVER = "mail.geekadomicile.com"
IMAP_PORT = 993
EMAIL_USER = "ykassine-test@geekadomicile.com"
EMAIL_PASS = "JHygR4P8"


def connect_imap():
    """Connect to IMAP server and login."""
    print(f"Connecting to {IMAP_SERVER}:{IMAP_PORT}...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_USER, EMAIL_PASS)
    print("Connected successfully!")
    return mail


def list_folders(mail):
    """List all available mailbox folders."""
    status, folders = mail.list()
    print("\n=== Mailbox Folders ===")
    for folder in folders:
        print(f"  {folder.decode()}")
    return folders


def decode_mime_header(header_value):
    """Decode a MIME-encoded header into a readable string."""
    if header_value is None:
        return ""
    decoded_parts = decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def get_email_body(msg):
    """Extract the text body from an email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
                break
            elif content_type == "text/html" and not body:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    return body


def fetch_recent_emails(mail, folder="INBOX", count=10):
    """Fetch the most recent emails from a folder."""
    mail.select(folder)
    status, messages = mail.search(None, "ALL")

    if status != "OK":
        print(f"Error searching {folder}")
        return []

    msg_ids = messages[0].split()
    total = len(msg_ids)
    print(f"\n=== {folder}: {total} total emails ===")

    if total == 0:
        print("  (empty)")
        return []

    # Get the last N emails
    recent_ids = msg_ids[-count:]
    emails_data = []

    for msg_id in recent_ids:
        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        email_info = {
            "id": msg_id.decode(),
            "from": decode_mime_header(msg["From"]),
            "to": decode_mime_header(msg["To"]),
            "subject": decode_mime_header(msg["Subject"]),
            "date": msg["Date"],
            "body": get_email_body(msg),
        }
        emails_data.append(email_info)

        print(f"\n--- Email #{email_info['id']} ---")
        print(f"  From:    {email_info['from']}")
        print(f"  To:      {email_info['to']}")
        print(f"  Subject: {email_info['subject']}")
        print(f"  Date:    {email_info['date']}")
        print(f"  Body preview: {email_info['body'][:200]}...")
        print()

    return emails_data


def main():
    mail = None
    try:
        mail = connect_imap()
        list_folders(mail)
        emails = fetch_recent_emails(mail, "INBOX", count=10)
        print(f"\nFetched {len(emails)} emails total.")
        return emails
    except imaplib.IMAP4.error as e:
        print(f"IMAP Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if mail:
            mail.logout()
            print("\nDisconnected.")


if __name__ == "__main__":
    main()
