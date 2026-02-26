"""
Parsing email — Geekadomicile Email Timeline

Fonctions pures d'extraction de contenu : nettoyage du body,
parsing de dates, extraction de montants.
"""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from config import MAX_CLEAN_LINES


def parse_email_date(date_str):
    """Parse une date d'en-tête email RFC 2822.

    Returns:
        datetime ou None si parsing impossible.
    """
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def sortable_dt(dt):
    """Normalise un datetime pour le tri (retire le tzinfo).

    Note: ne convertit pas en UTC, utilise le temps local tel quel.
    Pour un tri fiable multi-timezone, convertir d'abord en UTC.
    """
    if dt is None:
        return datetime.min
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def extract_clean_body(body):
    """Extrait la partie significative d'un email (supprime citations, signatures).

    Supprime :
    - Lignes citées (commençant par >)
    - JSON de logs téléphoniques
    - Citations "On ... wrote:" / "Le ..."
    - Signature (après --)
    - Numéros de téléphone bruts et URLs longues
    """
    lines = body.split("\n")
    clean_lines = []

    for line in lines:
        stripped = line.strip()

        # Citations
        if stripped.startswith(">"):
            continue
        # JSON de logs téléphoniques
        if stripped.startswith('{"Called"') or stripped.startswith('{&quot;Called'):
            continue

        # Début de citation (on arrête)
        if re.match(r'^On \d+/\d+/\d+.*wrote:', stripped):
            break
        if re.match(r'^\d+ \w+\.? \d{4} \d+:\d+', stripped):
            break
        if re.match(r'^Le \d+/\d+/\d+', stripped):
            break

        # Signature
        if stripped == "--" or stripped == "-- ":
            break

        # Numéros de téléphone bruts
        if re.match(r'^\+\d{10,}$', stripped):
            continue
        # URLs très longues
        if re.match(r'^https?://\S{80,}$', stripped):
            continue

        if stripped:
            clean_lines.append(line.rstrip())

    return "\n".join(clean_lines[:MAX_CLEAN_LINES])


def extract_amount_from_subject(subject):
    """Extrait un montant en euros depuis un sujet email.

    Exemples: "chq 78EUR", "chq 135€", "devis 250,50 eur"

    Returns:
        str du montant ou None.
    """
    match = re.search(r'(\d+[\.,]?\d*)\s*(?:eur|EUR|\u20ac)', subject or "")
    return match.group(1) if match else None
