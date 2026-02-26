"""
Configuration — Geekadomicile Email Timeline

Constantes centralisées : couleurs par type d'échange, icônes équipement,
labels de catégories, et seuils nommés.
"""

import os
import json

# -- Chemins --
BASE_DIR = os.path.dirname(__file__)
CLIENTS_FILE = os.path.join(BASE_DIR, "clients.json")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "attachments")

# -- Seuils nommés (remplace les magic numbers) --
MAX_BODY_PREVIEW_CHARS = 300    # Nb de caractères du body analysés pour classification
MAX_CLEAN_LINES = 30            # Nb max de lignes gardées dans le corps nettoyé
CALL_DEDUP_THRESHOLD_SEC = 300  # Fenêtre de 5 min pour matcher appels IMAP ↔ call log
HASH_PREFIX_LEN = 8             # Longueur du préfixe hash pour noms de fichiers attachés

# -- Couleurs par type d'échange (utilisées dans les badges et filtres) --
COLORS = {
    "call_incoming":  "#e74c3c",
    "call_outgoing":  "#e67e22",
    "call_missed":    "#c0392b",
    "call_note":      "#e67e22",
    "internal_note":  "#f39c12",
    "quote":          "#1abc9c",
    "quote_accepted": "#16a085",
    "quote_reply":    "#1abc9c",
    "invoice":        "#9b59b6",
    "invoice_unpaid": "#8e44ad",
    "payment":        "#27ae60",
    "accounting":     "#8e44ad",
    "client_email":   "#3498db",
    "reply":          "#7f8c8d",
    "followup":       "#2980b9",
    "callback":       "#2c3e50",
    "calendar":       "#0097a7",
    "timecop":        "#ff6f00",
    "other":          "#95a5a6",
}

DEFAULT_COLOR = "#95a5a6"

# -- Équipements : icônes HTML et labels par catégorie --
EQ_ICONS = {
    "smartphone":   "&#128241;",
    "tablette":     "&#128195;",
    "uc":           "&#128187;",
    "tout_en_un":   "&#128421;",
    "portable":     "&#128187;",
    "imprimante":   "&#128424;",
    "reseau":       "&#127760;",
    "peripherique": "&#9000;",
    "logiciel":     "&#128190;",
    "compte":       "&#128100;",
}

EQ_CAT_LABELS = {
    "smartphone":   "Smartphones",
    "tablette":     "Tablettes",
    "uc":           "UC Fixes",
    "tout_en_un":   "Tout-en-un",
    "portable":     "Portables",
    "imprimante":   "Imprimantes",
    "reseau":       "Réseau",
    "peripherique": "Périphériques",
    "logiciel":     "Logiciels",
    "compte":       "Comptes",
}

# Ordre d'affichage des catégories dans le panneau équipements
EQ_CAT_ORDER = [
    "smartphone", "tablette", "uc", "tout_en_un", "portable",
    "imprimante", "reseau", "peripherique", "logiciel", "compte",
]

# -- Dossiers IMAP à scanner --
IMAP_FOLDERS = [
    "INBOX", "Sent",
    "Archive.2022", "Archive.2023", "Archive.2024",
    "Archive.2025", "Archive.2026", "Archives.2026",
    "Archive.1970",
]

# -- Extensions fichiers images --
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
DOC_EXTENSIONS = ('.pdf', '.doc', '.docx', '.odt')


def load_clients():
    """Charge la liste de clients depuis clients.json."""
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("clients", [])
