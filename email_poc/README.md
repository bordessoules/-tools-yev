# Email Timeline — Geekadomicile

Outil interne de visualisation chronologique des échanges client pour [Geekadomicile](https://geekadomicile.com), atelier de réparation informatique à Versailles.

## Fonctionnalités

- **Timeline chronologique** — emails, appels, RDV, temps de travail, devis, factures
- **Détection d'équipements** — extraction automatique des appareils mentionnés
- **OCR / extraction de texte** — images (Qwen VL), PDF (pypdf), DOCX
- **Filtres multi-sélection** — par type d'échange et par équipement
- **Overlay split-view** — aperçu pièce jointe + texte OCR côte à côte
- **Panneau équipements** — inventaire avec regroupement et liaison Django

## Architecture

```
client_timeline.py       # Point d'entrée — orchestre le pipeline
config.py                # Constantes, couleurs, labels, seuils
models.py                # Dataclasses typées (Exchange, Client, Attachment)
email_classifier.py      # Classification email (type + matching client)
email_parser.py          # Nettoyage body, parsing date, extraction montant
attachment_handler.py    # Extraction pièces jointes, icônes, formatage
data_fetcher.py          # I/O : IMAP, CalDAV, TimeCop, journal d'appels
html_generator.py        # Rendu Jinja2 avec filtres personnalisés

templates/
  timeline.html          # Template principal
  partials/
    exchange_rows.html   # Lignes de la timeline
    attachments.html     # Pièces jointes (miniatures + fichiers)
    equipment_panel.html # Panneau inventaire équipements

static/
  timeline.css           # Styles
  timeline.js            # Filtres, recherche, overlay, regroupement

Connecteurs externes (inchangés) :
  fetch_emails.py        # Connexion IMAP
  equipment_extractor.py # Extraction d'équipements depuis les notes
  ocr_connector.py       # OCR images (LM Studio / Qwen VL) + PDF/DOCX
  cloud_connector.py     # Événements calendrier (CalDAV)
  timecop_connector.py   # Sessions TimeCop
  calllog_connector.py   # Journal d'appels
```

## Utilisation

```bash
pip install -r requirements.txt
python client_timeline.py
python -m http.server 8765
# Ouvrir http://localhost:8765/timeline_<client-id>.html
```

## Configuration

Créer `clients.json` :

```json
{
  "clients": [
    {
      "id": "nom-prenom",
      "name": "Prénom Nom",
      "phones": ["+33..."],
      "emails": ["email@example.com"],
      "address": "..."
    }
  ]
}
```

## Prochaine étape

Intégration Django avec l'inventaire existant (voir GOALS.md).
