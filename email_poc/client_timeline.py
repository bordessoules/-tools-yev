"""
Client Timeline — Geekadomicile Email Timeline (v6 — refactored)

Point d'entrée : récupère les données de toutes les sources,
les fusionne et génère une timeline HTML par client.
"""

import os

from config import load_clients
from email_parser import sortable_dt
from data_fetcher import (
    fetch_all_client_emails,
    fetch_client_calendar_events,
    fetch_client_timecop_sessions,
    enrich_and_merge_call_log,
)
from html_generator import generate_html, generate_index_html


def main():
    clients = load_clients()
    if not clients:
        print("No clients found in clients.json")
        return

    base_dir = os.path.dirname(__file__)
    counts = {}

    for client in clients:
        print(f"\nProcessing client: {client['name']}...")

        # 1. Récupérer les données de chaque source
        exchanges = fetch_all_client_emails(client)
        print(f"  Found {len(exchanges)} emails")

        cal_events = fetch_client_calendar_events(client)
        print(f"  Found {len(cal_events)} calendar events")

        timecop_events = fetch_client_timecop_sessions(client)
        print(f"  Found {len(timecop_events)} TimeCop sessions")

        call_log_events = enrich_and_merge_call_log(exchanges, client)

        # 2. Fusionner et trier chronologiquement
        all_items = exchanges + cal_events + timecop_events + call_log_events
        all_items.sort(key=lambda x: sortable_dt(x["date"]))
        counts[client["id"]] = len(all_items)
        print(f"  Total: {len(all_items)} items")

        # 3. Générer le HTML de la timeline
        html = generate_html(client, all_items)
        filepath = os.path.join(base_dir, f"timeline_{client['id']}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Generated: {filepath}")

    # 4. Générer la page d'accueil
    clients_data = [{"client": c, "count": counts.get(c["id"], 0)} for c in clients]
    index_html = generate_index_html(clients_data)
    index_path = os.path.join(base_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"\nGenerated index: {index_path}")


if __name__ == "__main__":
    main()
