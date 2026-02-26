"""
Découverte de contacts — Geekadomicile Email Timeline

Scanne le carnet d'adresses CardDAV (Nextcloud) et liste les contacts
disponibles. Permet d'ajouter les sélectionnés à clients.json.
"""

import json
import re
import unicodedata

from cloud_connector import fetch_contacts
from config import CLIENTS_FILE, load_clients


def _slugify(name):
    """Convertit un nom en slug pour l'ID client (ex: 'Jean Dupont' → 'dupont-jean')."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii").lower()
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[-1]}-{parts[0]}"
    return parts[0] if parts else "unknown"


def _normalize_phone(phone):
    """Normalise un numéro de téléphone au format +33."""
    p = re.sub(r'[\s\-\.]', '', phone)
    if p.startswith("0") and len(p) == 10:
        p = "+33" + p[1:]
    return p


ADDRESSBOOKS = ["contacts", "z-app-generated--contactsinteraction--recent"]


def scan_carddav():
    """Récupère tous les contacts CardDAV (tous carnets) et filtre les internes.

    Returns:
        list de Contact (cloud_connector.Contact dataclass), dédupliqué par email
    """
    seen_emails = set()
    filtered = []

    for book in ADDRESSBOOKS:
        try:
            contacts = fetch_contacts(book)
            print(f"  {book}: {len(contacts)} contacts")
        except Exception as e:
            print(f"  {book}: erreur ({e})")
            continue

        for c in contacts:
            if not c.full_name:
                continue
            if "geekadomicile" in c.full_name.lower():
                continue
            # Dédupliquer par email
            c_emails = {e.lower() for e in c.emails}
            if c_emails & seen_emails:
                continue
            seen_emails |= c_emails
            filtered.append(c)

    return filtered


def display_and_select(contacts):
    """Affiche le tableau de contacts CardDAV et retourne les sélectionnés.

    Returns:
        list de dicts prêts pour clients.json
    """
    # Charger les clients existants pour les exclure
    existing = load_clients()
    existing_ids = {c["id"] for c in existing}
    known_emails = set()
    for c in existing:
        for e in c.get("emails", []):
            known_emails.add(e.lower())

    # Filtrer les contacts déjà dans clients.json
    available = []
    for c in contacts:
        slug = _slugify(c.full_name)
        emails_lower = {e.lower() for e in c.emails}
        if slug in existing_ids or emails_lower & known_emails:
            continue
        available.append(c)

    if not available:
        print("\nAucun nouveau contact trouvé (tous déjà dans clients.json).")
        return []

    # Affichage
    print(f"\nContacts CardDAV disponibles ({len(available)}) :\n")
    print(f" {'#':>3}  {'Nom':<25} {'Tel':<18} {'Email':<30} {'Adresse'}")
    print(f" {'---':>3}  {'---':<25} {'---':<18} {'---':<30} {'---'}")
    for i, c in enumerate(available, 1):
        tel = c.phones[0] if c.phones else "-"
        email = c.emails[0] if c.emails else "-"
        addr = c.address[:40] if c.address else "-"
        print(f" {i:>3}  {c.full_name:<25} {tel:<18} {email:<30} {addr}")

    # Sélection
    print("\nEntrez les numéros à ajouter (ex: 1,3) ou 'all' pour tous, 'q' pour quitter :")
    choice = input("> ").strip()
    if choice.lower() == "q" or not choice:
        return []

    if choice.lower() == "all":
        indices = range(len(available))
    else:
        indices = []
        for num_str in choice.split(","):
            try:
                idx = int(num_str.strip()) - 1
                if 0 <= idx < len(available):
                    indices.append(idx)
            except ValueError:
                pass

    selected = []
    for idx in indices:
        c = available[idx]
        phones = [_normalize_phone(p) for p in c.phones]
        selected.append({
            "id": _slugify(c.full_name),
            "name": c.full_name,
            "emails": c.emails,
            "phones": phones,
            "address": c.address,
        })

    return selected


def add_clients_to_json(new_clients):
    """Ajoute les nouveaux clients à clients.json."""
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_ids = {c["id"] for c in data.get("clients", [])}
    added = 0
    for client in new_clients:
        if client["id"] in existing_ids:
            print(f"  Ignoré (ID déjà existant) : {client['id']}")
            continue
        data["clients"].append(client)
        added += 1
        emails_str = client["emails"][0] if client["emails"] else "-"
        print(f"  Ajoute : {client['name']} ({emails_str}) -> id={client['id']}")

    if added:
        with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n{added} client(s) ajouté(s) à {CLIENTS_FILE}")
        print("Lancez 'python client_timeline.py' pour générer leurs timelines.")
    else:
        print("\nAucun client ajouté.")


def main():
    print("Récupération des contacts CardDAV (Nextcloud)...\n")
    contacts = scan_carddav()
    print(f"Total : {len(contacts)} contacts trouvés")

    selected = display_and_select(contacts)
    if selected:
        add_clients_to_json(selected)


if __name__ == "__main__":
    main()
