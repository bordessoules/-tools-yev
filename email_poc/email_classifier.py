"""
Classification email — Geekadomicile Email Timeline

Détermine le type d'un email (appel, note interne, devis, facture…)
et vérifie si un email concerne un client donné.
"""

import re
from config import MAX_BODY_PREVIEW_CHARS


def email_matches_client(msg_from, msg_to, subject, body, client):
    """Vérifie si un email concerne un client donné.

    Critères de matching (exact uniquement) :
    - Adresse email du client dans from/to/subject
    - Nom complet du client dans l'en-tête
    - Partie du nom (> 3 cars) dans le sujet
    - Numéro de téléphone dans le body
    """
    all_text = f"{msg_from} {msg_to} {subject}".lower()

    for addr in client.get("emails", []):
        if addr.lower() in all_text:
            return True

    name = client.get("name", "").lower()
    if name and name in all_text:
        return True

    for part in name.split():
        if len(part) > 3 and part in subject.lower():
            return True

    for phone in client.get("phones", []):
        if phone in body:
            return True

    return False


def classify_email(msg_from, msg_to, subject, body):
    """Classifie le type d'un email selon l'expéditeur, le destinataire et le sujet.

    Returns:
        tuple (type_key, type_label) — ex: ("call_note", "Appel + Note")
    """
    from_lower = msg_from.lower()
    to_lower = (msg_to or "").lower()
    subj_lower = (subject or "").lower()
    body_lower = body.lower()[:MAX_BODY_PREVIEW_CHARS]

    # Notes internes et comptes-rendus d'appel (envoyés aux boîtes internes)
    if "ttt@geekadomicile" in to_lower or "cr@geekadomicile" in to_lower:
        if "appel entrant" in subj_lower:
            return "call_note", "Appel + Note"
        return "internal_note", "Note interne"

    # Appels entrants (depuis le système téléphonique)
    if "incall@" in from_lower:
        return "call_incoming", "Appel entrant"

    # Comptabilité (chèques, envois au comptable)
    if "comptable@" in to_lower or "chq " in subj_lower:
        return "accounting", "Comptabilite"

    # Factures
    if "facture non acquitt" in subj_lower:
        return "invoice_unpaid", "Facture impayee"
    if "facture" in subj_lower:
        return "invoice", "Facture"

    # Paiements
    if "paiement" in subj_lower or "e-transactions" in from_lower:
        return "payment", "Paiement"

    # Devis et interventions
    if "intervention" in subj_lower or "proposition maintenance" in subj_lower:
        return "quote", "Devis"
    if "geekadomicile :" in subj_lower and not any(
        w in subj_lower for w in ("facture", "paiement", "suivi")
    ):
        if "bon pour accord" in body_lower:
            return "quote_accepted", "Accord client"
        if "geekadomicile" in from_lower:
            return "quote", "Devis"
        return "quote_reply", "Reponse devis"

    # Suivi
    if "suivi" in subj_lower:
        return "followup", "Suivi"

    # Demande de rappel
    if "demande de rappel" in subj_lower:
        return "callback", "Demande rappel"

    # Email client (expéditeur externe)
    if "geekadomicile" not in from_lower and "incall@" not in from_lower:
        return "client_email", "Email client"

    # Réponse Geekadomicile
    if "geekadomicile" in from_lower:
        return "reply", "Reponse"

    return "other", "Autre"
