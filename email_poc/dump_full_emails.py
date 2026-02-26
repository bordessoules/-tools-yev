"""
Dump full email bodies to understand the complete Twilio JSON structure.
"""

import imaplib
import email
import json
from urllib.parse import unquote
from fetch_emails import connect_imap, decode_mime_header, get_email_body


def dump_all_call_emails(mail):
    """Find and dump all call notification emails across folders."""
    folders = ["INBOX", "Sent", "Archive.2025", "Archive.2026"]

    for folder in folders:
        try:
            mail.select(folder, readonly=True)
            status, messages = mail.search(None, 'FROM', '"incall@geekadomicile.com"')
            if status != "OK":
                continue
            msg_ids = messages[0].split()
            if not msg_ids:
                # Also search in sent for replies
                status, messages = mail.search(None, 'SUBJECT', '"Appel entrant"')
                msg_ids = messages[0].split()
            if not msg_ids:
                continue

            print(f"\n{'='*60}")
            print(f"FOLDER: {folder} ({len(msg_ids)} matching emails)")
            print(f"{'='*60}")

            for msg_id in msg_ids[:3]:  # First 3 per folder
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                body = get_email_body(msg)
                subject = decode_mime_header(msg["Subject"])
                sender = decode_mime_header(msg["From"])

                print(f"\n--- {subject} ---")
                print(f"From: {sender}")
                print(f"Full body:\n{body}\n")

                # Try to extract and pretty-print JSON
                if "{" in body:
                    try:
                        json_start = body.index("{")
                        json_end = body.rindex("}") + 1
                        json_str = body[json_start:json_end]
                        # URL decode if needed
                        json_str = unquote(json_str)
                        data = json.loads(json_str)
                        print("Parsed JSON:")
                        print(json.dumps(data, indent=2))
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"Could not parse JSON: {e}")

        except Exception as e:
            print(f"Error with {folder}: {e}")


def main():
    mail = connect_imap()
    dump_all_call_emails(mail)
    mail.logout()


if __name__ == "__main__":
    main()
