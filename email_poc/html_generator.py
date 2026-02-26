"""
Génération HTML — Geekadomicile Email Timeline

Prépare les données et rend le template Jinja2 avec les partials.
Tout le HTML est dans les templates, pas en Python.
"""

import os
from html import escape
from jinja2 import Environment, FileSystemLoader

from ocr_connector import load_all_ocr_results
from email_parser import sortable_dt
from attachment_handler import att_icon, format_size, is_image
from config import (
    TEMPLATE_DIR, ATTACHMENTS_DIR, COLORS, DEFAULT_COLOR,
    EQ_ICONS, EQ_CAT_LABELS, EQ_CAT_ORDER, DOC_EXTENSIONS, IMAGE_EXTENSIONS,
)


def _build_type_filters(exchanges):
    """Construit la liste de filtres par type avec compteurs.

    Returns:
        list de dicts {type_key, label, count, color}, triée par fréquence.
    """
    seen = {}
    for ex in exchanges:
        key = ex["type"]
        if key not in seen:
            seen[key] = {
                "type_key": key,
                "label": ex["type_label"],
                "count": 0,
                "color": COLORS.get(key, DEFAULT_COLOR),
            }
        seen[key]["count"] += 1
    return sorted(seen.values(), key=lambda x: -x["count"])


def _build_equipment_data(exchanges):
    """Prépare les données du panneau équipements (occurrences par catégorie).

    Returns:
        (eq_by_cat dict, eq_occurrences list, total int)
    """
    occurrences = []
    for ex_i, ex in enumerate(exchanges):
        for eq in ex.get("equipments", []):
            occurrences.append({
                "equipment": eq,
                "date": ex["date"],
                "type_label": ex["type_label"],
                "exchange_idx": ex_i,
            })
    occurrences.sort(key=lambda o: sortable_dt(o["date"]), reverse=True)

    # Ajouter un index global pour les boutons de liaison
    eq_by_cat = {}
    for idx, occ in enumerate(occurrences):
        occ["global_idx"] = idx
        eq_by_cat.setdefault(occ["equipment"].category, []).append(occ)

    return eq_by_cat, occurrences, len(occurrences)


# -- Filtres Jinja2 personnalisés --

def _filter_format_size(size):
    return format_size(size)

def _filter_att_icon(content_type, filename):
    return att_icon(content_type, filename)

def _filter_is_image_ext(filename):
    return filename.lower().endswith(IMAGE_EXTENSIONS)

def _filter_is_doc(filename):
    return filename.lower().endswith(DOC_EXTENSIONS)

def _filter_is_pdf(filename):
    return filename.lower().endswith('.pdf')


# -- Environnement Jinja2 --

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,          # Protection XSS activée
    extensions=['jinja2.ext.do'],
)
_jinja_env.filters['format_size'] = _filter_format_size
_jinja_env.filters['att_icon_filter'] = _filter_att_icon
_jinja_env.filters['is_image_ext'] = _filter_is_image_ext
_jinja_env.filters['is_doc'] = _filter_is_doc
_jinja_env.filters['is_pdf'] = _filter_is_pdf


def generate_index_html(clients_with_counts):
    """Génère la page d'accueil avec la liste des clients.

    Args:
        clients_with_counts: list de dicts {client: {...}, count: int}

    Returns:
        str HTML complet de la page index.
    """
    template = _jinja_env.get_template("index.html")
    return template.render(clients=clients_with_counts)


def generate_html(client, exchanges):
    """Génère le HTML complet de la timeline via le template Jinja2.

    Args:
        client: dict client {id, name, phones, emails, address}
        exchanges: list de dicts d'échange triée chronologiquement

    Returns:
        str HTML complet de la page.
    """
    client_id = client.get("id", "unknown")

    # Charger les résultats OCR
    att_dir = os.path.join(ATTACHMENTS_DIR, client_id)
    ocr_results = load_all_ocr_results(att_dir)
    if ocr_results:
        print(f"  Loaded {len(ocr_results)} OCR results")

    # Données équipements
    eq_by_cat, eq_occurrences, eq_total = _build_equipment_data(exchanges)

    template = _jinja_env.get_template("timeline.html")

    return template.render(
        # En-tête client
        client_name=client["name"],
        phones=", ".join(client.get("phones", [])),
        emails=", ".join(client.get("emails", [])),
        address=client.get("address", ""),
        total_events=len(exchanges),

        # Filtres
        type_filters=_build_type_filters(exchanges),

        # Timeline (ordre inversé pour afficher du plus récent au plus ancien)
        exchanges_reversed=list(reversed(exchanges)),
        total=len(exchanges),
        colors=COLORS,
        default_color=DEFAULT_COLOR,
        eq_icons=EQ_ICONS,

        # Équipements
        client_id=client_id,
        ocr_results=ocr_results,
        eq_by_cat=eq_by_cat,
        eq_occurrences=eq_occurrences,
        eq_total=eq_total,
        eq_cat_order=EQ_CAT_ORDER,
        eq_cat_labels=EQ_CAT_LABELS,
    )
