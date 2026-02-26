# Objectifs du projet

## Contexte

Geekadomicile gère des clients avec de multiples canaux de communication (email, téléphone, RDV, notes internes). L'information est dispersée entre boîte mail, calendrier, TimeCop et journal d'appels. Cet outil rassemble tout dans une vue unifiée par client.

## Phase 1 — POC ✅

- [x] Récupération emails IMAP (INBOX, Sent, Archives)
- [x] Classification automatique (appel, note interne, devis, facture, réponse…)
- [x] Timeline HTML chronologique avec code couleur par type
- [x] Recherche plein texte
- [x] Intégration calendrier CalDAV
- [x] Intégration TimeCop (suivi temps)
- [x] Intégration journal d'appels (entrants, sortants, manqués + durée)
- [x] Détection d'équipements dans les notes internes
- [x] Extraction de texte : OCR images (Qwen VL), PDF (pypdf), DOCX
- [x] Miniatures des images jointes
- [x] Extraction de montants depuis les sujets (devis, factures, chèques)

## Phase 2 — Restructuration ✅

- [x] Séparation CSS / JS / HTML template (Jinja2)
- [x] Filtres multi-sélection par type d'échange
- [x] Filtres multi-sélection par équipement
- [x] Overlay split-view pièces jointes (image/PDF + OCR)
- [x] Dissociation de groupes d'équipements liés par erreur

## Phase 2b — Nettoyage du code ✅

- [x] Modèle de données typé (dataclasses)
- [x] Découpage en modules (config, classifier, parser, handler, fetcher, generator)
- [x] HTML dans les templates Jinja2 (partials), plus en Python
- [x] Autoescape Jinja2 activé (protection XSS)
- [x] JavaScript sécurisé (escHtml, IIFE, selector injection fixé)
- [x] Constantes nommées, commentaires, docstrings

## Phase 3 — Intégration Django

- [ ] Intégrer les templates Jinja2 comme templates Django
- [ ] Lier les équipements détectés à l'inventaire Django existant
- [ ] Persister les liens équipement ↔ inventaire en base de données
- [ ] Vue client accessible depuis l'interface d'administration
- [ ] API REST pour la timeline (JSON) si besoin front séparé

## Phase 4 — Améliorations futures

- [ ] Mise à jour incrémentale (ne pas refetcher tous les emails à chaque fois)
- [ ] Notifications / alertes (factures impayées, rappels en attente)
- [ ] Recherche avancée (par date, par montant, par équipement)
- [ ] Export PDF de la timeline client
- [ ] Multi-utilisateur / multi-technicien
