"""
Explore all email exchanges to understand the full conversation patterns.
Look at both incoming and outgoing emails, threading by subject/references.
"""

import imaplib
import email
from email.header import decode_header
from fetch_emails import connect_imap, decode_mime_header, get_email_body


def fetch_all_emails(mail, folder):
    """Fetch all emails from a folder with full details."""
    emails = []
    try:
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            return emails
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return emails
        msg_ids = messages[0].split()
        for msg_id in msg_ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            body = get_email_body(msg)
            emails.append({
                "folder": folder,
                "msg_id": msg_id.decode(),
                "from": decode_mime_header(msg["From"]),
                "to": decode_mime_header(msg["To"]),
                "subject": decode_mime_header(msg["Subject"]),
                "date": msg["Date"],
                "message_id": msg["Message-ID"],
                "in_reply_to": msg["In-Reply-To"],
                "references": msg["References"],
                "body": body,
            })
    except Exception as e:
        print(f"Error with {folder}: {e}")
    return emails


def main():
    mail = connect_imap()
    all_emails = []
    for folder in ["INBOX", "Sent", "Archive.2025", "Archive.2026", "Archives.2026"]:
        msgs = fetch_all_emails(mail, folder)
        all_emails.extend(msgs)
        print(f"{folder}: {len(msgs)} emails")
    mail.logout()

    print(f"\nTotal: {len(all_emails)} emails")

    # Group by subject thread (strip Re:/Fwd: prefixes)
    import re
    threads = {}
    for em in all_emails:
        subj = em["subject"] or "(no subject)"
        # Normalize subject: strip Re:/Fwd: prefixes
        clean_subj = re.sub(r'^(Re:\s*|Fwd?:\s*)+', '', subj, flags=re.IGNORECASE).strip()
        if clean_subj not in threads:
            threads[clean_subj] = []
        threads[clean_subj].append(em)

    print(f"\n{len(threads)} conversation threads found:\n")

    for subj, msgs in sorted(threads.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{'='*70}")
        print(f"THREAD: {subj} ({len(msgs)} messages)")
        print(f"{'='*70}")

        # Sort by date
        for msg in sorted(msgs, key=lambda m: m["date"] or ""):
            sender = msg["from"]
            # Shorten sender
            if "<" in sender:
                name = sender.split("<")[0].strip()
            else:
                name = sender
            direction = ">>>" if "geekadomicile" in sender.lower() else "<<<"

            # Get first meaningful lines of body (skip quoted content)
            body_lines = []
            for line in msg["body"].split("\n"):
                stripped = line.strip()
                if stripped.startswith(">"):
                    continue
                if stripped.startswith("On ") and "wrote:" in stripped:
                    break
                if re.match(r'^\d+ \w+\.? \d{4}', stripped):
                    break
                if stripped == "--":
                    break
                if stripped:
                    body_lines.append(stripped)

            body_preview = "\n      ".join(body_lines[:5])

            print(f"\n  {direction} {msg['date']}")
            print(f"     From: {name}")
            print(f"     To:   {msg['to']}")
            print(f"     [{msg['folder']}]")
            if body_preview:
                print(f"     ---")
                print(f"      {body_preview}")


if __name__ == "__main__":
    main()
