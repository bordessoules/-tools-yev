"""
Récupération de données — Geekadomicile Email Timeline

Fonctions I/O : IMAP (emails), CalDAV (agenda), TimeCop (temps), journal d'appels.
Chaque source est transformée en dict d'échange unifié.
"""

import email
import re

from fetch_emails import connect_imap, decode_mime_header, get_email_body
from equipment_extractor import extract_equipment_from_note
from cloud_connector import fetch_calendar_events_for_client
from timecop_connector import fetch_timecop_for_client
from calllog_connector import fetch_calls_for_client

from email_classifier import email_matches_client, classify_email
from email_parser import parse_email_date, extract_clean_body, extract_amount_from_subject, sortable_dt
from attachment_handler import extract_attachments
from config import IMAP_FOLDERS, CALL_DEDUP_THRESHOLD_SEC


def fetch_all_client_emails(client):
    """Récupère tous les emails d'un client depuis tous les dossiers IMAP.

    Parcourt chaque dossier, télécharge tous les messages et ne garde
    que ceux qui correspondent au client (via email_matches_client).
    Déduplique par Message-ID.

    Returns:
        list de dicts d'échange, triée chronologiquement.
    """
    mail = connect_imap()
    all_exchanges = []
    seen_message_ids = set()
    client_id = client.get("id", "unknown")

    for folder in IMAP_FOLDERS:
        try:
            status, _ = mail.select(folder, readonly=True)
            if status != "OK":
                continue
            status, messages = mail.search(None, "ALL")
            if status != "OK":
                continue

            for msg_id in messages[0].split():
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])

                # Déduplication par Message-ID
                message_id = msg["Message-ID"]
                if message_id and message_id in seen_message_ids:
                    continue
                if message_id:
                    seen_message_ids.add(message_id)

                body = get_email_body(msg)
                msg_from = decode_mime_header(msg["From"])
                msg_to = decode_mime_header(msg["To"]) or ""
                subject = decode_mime_header(msg["Subject"]) or ""

                if not email_matches_client(msg_from, msg_to, subject, body, client):
                    continue

                dt = parse_email_date(msg["Date"])
                email_type, type_label = classify_email(msg_from, msg_to, subject, body)
                clean_body = extract_clean_body(body)

                if "geekadomicile" in msg_from.lower() or "incall@" in msg_from.lower():
                    direction = "out"
                else:
                    direction = "in"

                name_match = re.match(r'^(.*?)\s*<', msg_from)
                sender_name = name_match.group(1).strip().strip('"') if name_match else msg_from

                # Extraction d'équipements (uniquement notes internes / CR appels)
                equipments = []
                if email_type in ("internal_note", "call_note"):
                    equipments = extract_equipment_from_note(body)

                attachments = extract_attachments(msg, client_id)

                all_exchanges.append({
                    "date": dt,
                    "date_str": msg["Date"],
                    "from": msg_from,
                    "sender_name": sender_name,
                    "to": msg_to,
                    "subject": subject,
                    "body": clean_body,
                    "full_body": body,
                    "type": email_type,
                    "type_label": type_label,
                    "direction": direction,
                    "folder": folder,
                    "amount": extract_amount_from_subject(subject),
                    "equipments": equipments,
                    "attachments": attachments,
                })

        except Exception as e:
            print(f"  Error with {folder}: {e}")

    mail.logout()
    all_exchanges.sort(key=lambda x: sortable_dt(x["date"]))
    return all_exchanges


def fetch_client_calendar_events(client):
    """Récupère les RDV CalDAV d'un client, convertis en dicts d'échange."""
    try:
        events = fetch_calendar_events_for_client(client)
    except Exception as e:
        print(f"  Error fetching calendar: {e}")
        return []

    exchanges = []
    for event in events:
        body_parts = []
        if event.location:
            body_parts.append(event.location.replace("\\,", ","))
        if event.description:
            body_parts.append(event.description)
        body = "\n".join(body_parts)

        exchanges.append({
            "date": event.parsed_date,
            "date_str": event.dtstart,
            "from": "",
            "sender_name": "",
            "to": "",
            "subject": event.summary,
            "body": body,
            "full_body": body,
            "type": "calendar",
            "type_label": "RDV",
            "direction": "cal",
            "folder": "calendar",
            "amount": None,
            "equipments": [],
        })

    return exchanges


def fetch_client_timecop_sessions(client):
    """Récupère les sessions TimeCop d'un client, converties en dicts d'échange."""
    try:
        entries = fetch_timecop_for_client(client)
    except Exception as e:
        print(f"  Error fetching TimeCop: {e}")
        return []

    exchanges = []
    for entry in entries:
        body_parts = [f"Duree: {entry.duration_display}"]
        if entry.project:
            body_parts.append(f"Projet: {entry.project}")
        if entry.end:
            body_parts.append(f"{entry.start.strftime('%H:%M')} - {entry.end.strftime('%H:%M')}")
        if entry.notes:
            body_parts.append(entry.notes)
        body = "\n".join(body_parts)

        exchanges.append({
            "date": entry.start,
            "date_str": entry.date,
            "from": "",
            "sender_name": "",
            "to": "",
            "subject": entry.description,
            "body": body,
            "full_body": body,
            "type": "timecop",
            "type_label": "Temps",
            "direction": "work",
            "folder": "timecop",
            "amount": None,
            "equipments": [],
            "duration_display": entry.duration_display,
        })

    return exchanges


def enrich_and_merge_call_log(exchanges, client):
    """Enrichit les appels existants avec la durée du journal et ajoute les appels manquants.

    Pour chaque call_incoming existant, cherche l'entrée correspondante dans le journal
    (même numéro, dans une fenêtre de CALL_DEDUP_THRESHOLD_SEC secondes).

    Returns:
        list de nouveaux dicts d'échange (appels non matchés).
    """
    try:
        call_entries = fetch_calls_for_client(client)
    except Exception as e:
        print(f"  Error fetching call log: {e}")
        return []

    if not call_entries:
        return []

    print(f"  Found {len(call_entries)} call log entries")

    incoming_exchanges = [ex for ex in exchanges if ex["type"] == "call_incoming"]
    matched_call_ids = set()

    # Matcher les appels IMAP avec le journal téléphonique
    for ex in incoming_exchanges:
        phone_match = re.search(r'\+\d{10,}', ex["subject"] or "")
        if not phone_match:
            continue
        ex_phone = phone_match.group(0)
        ex_date = ex["date"]
        if not ex_date:
            continue

        best, best_delta = None, None
        for i, call in enumerate(call_entries):
            if i in matched_call_ids or call.number != ex_phone or not call.date:
                continue
            delta = abs((sortable_dt(ex_date) - call.date).total_seconds())
            if delta <= CALL_DEDUP_THRESHOLD_SEC:
                if best_delta is None or delta < best_delta:
                    best, best_delta = i, delta

        if best is not None:
            matched_call_ids.add(best)
            call = call_entries[best]
            if call.duration_secs > 0:
                ex["duration_display"] = call.duration_display

    # Créer des échanges pour les appels non matchés
    new_exchanges = []
    for i, call in enumerate(call_entries):
        if i in matched_call_ids:
            continue

        body_parts = []
        if call.duration_secs > 0:
            body_parts.append(f"Duree: {call.duration_display}")
        body_parts.append(call.number)
        body = "\n".join(body_parts)

        new_exchanges.append({
            "date": call.date,
            "date_str": call.date.strftime("%Y-%m-%d %H:%M") if call.date else "",
            "from": call.display_name or call.number,
            "sender_name": call.display_name or call.number,
            "to": "",
            "subject": f"{call.call_type_label} {call.number}",
            "body": body,
            "full_body": body,
            "type": call.call_type_key,
            "type_label": call.call_type_label,
            "direction": call.direction,
            "folder": "call_log",
            "amount": None,
            "equipments": [],
            "duration_display": call.duration_display if call.duration_secs > 0 else None,
        })

    print(f"  Enriched {len(matched_call_ids)} existing calls with duration")
    print(f"  Added {len(new_exchanges)} new calls from phone log")
    return new_exchanges
