"""
Explore archive folders to find more email samples.
"""

import imaplib
import email
from email.header import decode_header
from fetch_emails import connect_imap, decode_mime_header, get_email_body


FOLDERS_TO_CHECK = [
    "Archive.2026",
    "Archive.2025",
    "Archives.2026",
    "Sent",
]


def explore_folder(mail, folder, count=5):
    """Check a folder for emails."""
    try:
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            print(f"  Could not open {folder}")
            return

        status, messages = mail.search(None, "ALL")
        msg_ids = messages[0].split()
        total = len(msg_ids)
        print(f"\n=== {folder}: {total} emails ===")

        if total == 0:
            return

        recent_ids = msg_ids[-count:]
        for msg_id in recent_ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = decode_mime_header(msg["Subject"])
            sender = decode_mime_header(msg["From"])
            date = msg["Date"]
            body = get_email_body(msg)
            print(f"\n  [{msg_id.decode()}] {date}")
            print(f"    From: {sender}")
            print(f"    Subject: {subject}")
            print(f"    Body: {body[:300]}")
            print()
    except Exception as e:
        print(f"  Error with {folder}: {e}")


def main():
    mail = connect_imap()
    for folder in FOLDERS_TO_CHECK:
        explore_folder(mail, folder, count=5)
    mail.logout()
    print("Done.")


if __name__ == "__main__":
    main()
