"""
Analyze all internal notes to understand how equipment is referenced.
Look at indentation patterns, equipment mentions, and structure.
"""

import imaplib
import email
import re
from fetch_emails import connect_imap, decode_mime_header, get_email_body


def fetch_notes():
    """Fetch all internal notes (to ttt@ or cr@) and call replies."""
    mail = connect_imap()
    notes = []
    seen = set()

    folders = ["INBOX", "Sent", "Archive.2022", "Archive.2023", "Archive.2024",
               "Archive.2025", "Archive.2026", "Archives.2026"]

    for folder in folders:
        try:
            status, _ = mail.select(folder, readonly=True)
            if status != "OK":
                continue
            status, messages = mail.search(None, "ALL")
            if status != "OK":
                continue
            msg_ids = messages[0].split()

            for msg_id in msg_ids:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])

                message_id = msg["Message-ID"]
                if message_id and message_id in seen:
                    continue
                if message_id:
                    seen.add(message_id)

                msg_to = decode_mime_header(msg["To"]) or ""
                msg_from = decode_mime_header(msg["From"]) or ""
                subject = decode_mime_header(msg["Subject"]) or ""

                # Only internal notes and call replies from you
                is_internal = "ttt@geekadomicile" in msg_to.lower() or "cr@geekadomicile" in msg_to.lower()
                is_call_reply = subject.lower().startswith("re:") and "appel entrant" in subject.lower()

                if not (is_internal or is_call_reply):
                    continue
                if "geekadomicile" not in msg_from.lower():
                    continue

                body = get_email_body(msg)

                # Strip quoted content
                clean_lines = []
                raw_lines = []  # Keep original with indentation
                for line in body.split("\n"):
                    if line.strip().startswith(">"):
                        continue
                    if line.strip().startswith('{"Called"'):
                        continue
                    if re.match(r'^On \d+/\d+/\d+', line.strip()):
                        break
                    if re.match(r'^\d+ \w+\.? \d{4} \d+:\d+', line.strip()):
                        break
                    if re.match(r'^Le \d+/\d+/\d+', line.strip()):
                        break
                    if line.strip() == "--" or line.strip() == "-- ":
                        break
                    if re.match(r'^\+\d{10,}$', line.strip()):
                        continue
                    if line.strip():
                        clean_lines.append(line.strip())
                        raw_lines.append(line)

                if not clean_lines:
                    continue

                notes.append({
                    "date": msg["Date"],
                    "subject": subject,
                    "clean": "\n".join(clean_lines),
                    "raw": "\n".join(raw_lines),
                })

        except Exception as e:
            print(f"Error with {folder}: {e}")

    mail.logout()
    return notes


def main():
    notes = fetch_notes()
    print(f"Found {len(notes)} notes\n")

    print("=" * 80)
    print("RAW NOTES WITH INDENTATION (repr to see tabs/spaces)")
    print("=" * 80)

    for note in notes:
        print(f"\n--- {note['date']} ---")
        print(f"Subject: {note['subject']}")
        print("Raw lines:")
        for line in note["raw"].split("\n"):
            # Show indentation character by character
            indent = ""
            for ch in line:
                if ch == "\t":
                    indent += "[TAB]"
                elif ch == " ":
                    indent += "[SP]"
                else:
                    break
            content = line.lstrip()
            if indent:
                print(f"  {indent}{content}")
            else:
                print(f"  {content}")
        print()


if __name__ == "__main__":
    main()
