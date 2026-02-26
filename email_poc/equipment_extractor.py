"""
Equipment Extractor v3
Parses repair notes to identify equipment/devices worked on.
Uses indentation (tab from PC, spaces from phone) to build a tree
and identify devices at the root level with their sub-details.

Also detects equipment in indented lines (level 1) when they clearly
name a device (e.g. after "ad:" or "pb:" header lines).

Equipment categories:
- smartphone: iPhone, Samsung, etc.
- tablette: iPad, Samsung Tab, etc.
- uc: Unite Centrale (desktop tower)
- tout_en_un: All-in-one desktop
- portable: Laptop
- imprimante: Printer/Scanner
- reseau: Network equipment (box, routeur, switch)
- peripherique: Peripherals (clavier, souris, ecran, moniteur)
- logiciel: Software-only intervention (no specific hardware)
- compte: User accounts (Orange, SFR, Gmail, etc.)
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Equipment:
    category: str
    raw_text: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    model_number: Optional[str] = None
    details: list = field(default_factory=list)

    @property
    def label(self):
        cat_labels = {
            'smartphone': 'Smartphone',
            'tablette': 'Tablette',
            'uc': 'UC Fixe',
            'tout_en_un': 'Tout-en-un',
            'portable': 'Portable',
            'imprimante': 'Imprimante',
            'reseau': 'Réseau',
            'peripherique': 'Périphérique',
            'logiciel': 'Logiciel',
            'compte': 'Compte',
        }
        parts = [cat_labels.get(self.category, self.category)]
        if self.brand:
            parts.append(self.brand)
        if self.model:
            parts.append(self.model)
        return " - ".join(parts)

    @property
    def display_name(self):
        if self.brand and self.model:
            return f"{self.brand} {self.model}"
        if self.brand:
            if self.serial:
                return f"{self.brand} (SN:{self.serial})"
            return self.brand
        if self.model:
            return self.model
        return self.raw_text.strip()[:50]

    @property
    def unique_key(self):
        """Normalized key for dedup."""
        parts = [self.category]
        if self.serial:
            parts.append(self.serial.lower())
        elif self.brand:
            parts.append(self.brand.lower())
            if self.model:
                parts.append(re.sub(r'\s+', '', self.model.lower()))
        elif self.model:
            # Software and other items without brand — use model for dedup
            parts.append(re.sub(r'\s+', '', self.model.lower()))
        return "|".join(parts)


def _extract_serial(text):
    m = re.search(r'sn:(\S+)', text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_model_number(text):
    m = re.search(r'mo:(\S+)', text, re.IGNORECASE)
    return m.group(1) if m else None


def _detect_equipment(text):
    """
    Detect equipment from a line. Only matches lines that clearly NAME
    a device, not describe a problem or action.
    Returns Equipment or None.
    """
    t = text.strip()
    tl = t.lower()

    # Skip lines that are problems/actions, not equipment names
    skip_starters = [
        'ne parvient', 'ne peut', 'ne fonctionne', 'erreur', 'pb ',
        'pb:', 'probleme', 'impossible', 'a perdu', 'veut ', 'comment ',
        'msg left', 'bon pour', 'paye', 'intervention', 'hospitalis',
        'livraison et', 'le clavier ne', 'le recepteur', 'a changé',
        'conversion', 'envoi', 'rdv ', 'appel ', 'dispo ', 'test ',
        'connexion ', 'activation ', 'reconnexi', 'remplacement',
        'desactivation', 'nettoyage', 'papier ', 'ajout ', 'aide ',
        'changer ', 'reinstall', 'imprime en', 'saisie ', 'a mis ',
        'fonctionne', 'perte ', 'a un sinistre', 'doit ', 'transmiss',
        'appel de', 'code client', 'mail de test', 'wifi:',
    ]
    for s in skip_starters:
        if tl.startswith(s):
            return None

    if tl.startswith('ad:') or tl.startswith('ad :'):
        return None
    if tl.startswith('mdp') or tl.startswith('id:') or tl.startswith('pin '):
        return None
    if re.match(r'^\d+ \w+ \d{4}', tl):
        return None
    if '@' in tl and 'imprimante' not in tl and not tl.startswith('compte '):
        return None

    serial = _extract_serial(t)
    model_no = _extract_model_number(t)

    # ─── Smartphones ───
    m = re.match(r'^(?:smartphone\s+(?:apple\s+)?)?(?:nouvel?\s+)?(iphone)\s*(\d+)?(?:\s+(pro|max|plus|mini))?',
                 tl)
    if m:
        model = "iPhone"
        if m.group(2):
            model += f" {m.group(2)}"
        if m.group(3):
            model += f" {m.group(3).capitalize()}"
        return Equipment(category='smartphone', raw_text=t, brand='Apple',
                         model=model, serial=serial)

    if re.match(r'^smartphone\s+apple\b', tl):
        return Equipment(category='smartphone', raw_text=t, brand='Apple',
                         model='iPhone', serial=serial)

    if re.match(r'^smartphone\b', tl):
        bm = re.search(r'smartphone\s+(\w+)\s*(.*)', tl)
        brand = bm.group(1).capitalize() if bm else None
        model = bm.group(2).strip() or None if bm else None
        return Equipment(category='smartphone', raw_text=t, brand=brand,
                         model=model, serial=serial)

    # ─── Tablettes ───
    if re.match(r'^(?:tablette\s+)?ipad\b', tl):
        return Equipment(category='tablette', raw_text=t, brand='Apple',
                         model='iPad', serial=serial)
    if re.match(r'^tablette\b', tl):
        return Equipment(category='tablette', raw_text=t, serial=serial)

    # ─── Imprimantes ───
    m = re.match(r'^imprimante\s+(hp|canon|epson|brother|samsung)\s+(.+?)(?:\s+sn:|\s+mo:|$)',
                 tl)
    if m:
        brand = m.group(1).upper() if m.group(1).lower() == 'hp' else m.group(1).capitalize()
        model = m.group(2).strip()
        model = re.sub(r'office\s*jet', 'OfficeJet', model, flags=re.IGNORECASE)
        # Clean trailing "series"
        model = re.sub(r'\s*series\s*$', '', model, flags=re.IGNORECASE)
        return Equipment(category='imprimante', raw_text=t, brand=brand,
                         model=model, serial=serial)

    if tl == 'imprimante':
        return Equipment(category='imprimante', raw_text=t, serial=serial)

    # ─── Network equipment ───
    m = re.match(r'^(?:nouvelle?\s+)?box\s+(?:internet\s+)?(sfr|orange|free|bouygues)\b', tl)
    if m:
        return Equipment(category='reseau', raw_text=t,
                         brand=m.group(1).upper(), model='Box Internet',
                         serial=serial)

    if re.match(r'^(?:nouvelle?\s+)?box\s+internet\b', tl):
        return Equipment(category='reseau', raw_text=t, model='Box Internet',
                         serial=serial)

    if re.match(r'^routeur\b', tl):
        return Equipment(category='reseau', raw_text=t, model='Routeur',
                         serial=serial)

    # ─── UC Fixe ───
    m = re.match(r'^(?:uc|ordinateur)\s+fixe\s+(lenovo|hp|dell|asus|acer)\s*(.*?)(?:\s+sn:|\s+mo:|$)',
                 tl)
    if m:
        brand = m.group(1).capitalize()
        model = m.group(2).strip() or None
        return Equipment(category='uc', raw_text=t, brand=brand, model=model,
                         serial=serial, model_number=model_no)

    if re.match(r'^(?:uc|ordinateur)\s+fixe\b', tl):
        return Equipment(category='uc', raw_text=t, serial=serial,
                         model_number=model_no)

    m = re.match(r'^uc\s+fixe\s+(\w+)', tl)
    if m:
        return Equipment(category='uc', raw_text=t,
                         brand=m.group(1).capitalize(), serial=serial)

    if tl == 'ordinateur':
        return Equipment(category='uc', raw_text=t)

    # ─── Portable ───
    m = re.match(r'^(?:ordinateur\s+)?portable\s+(lenovo|hp|dell|asus|acer|apple|macbook)\s*(.*)',
                 tl)
    if m:
        return Equipment(category='portable', raw_text=t,
                         brand=m.group(1).capitalize(),
                         model=m.group(2).strip() or None, serial=serial)

    if re.match(r'^(?:ordinateur\s+)?portable\b', tl):
        return Equipment(category='portable', raw_text=t, serial=serial)

    # ─── Tout-en-un ───
    if re.match(r'^imac\b', tl):
        return Equipment(category='tout_en_un', raw_text=t, brand='Apple',
                         model='iMac', serial=serial)
    if re.match(r'^tout[- ]en[- ]un\b', tl):
        return Equipment(category='tout_en_un', raw_text=t, serial=serial)

    # ─── Peripheriques ───
    m = re.match(r'^clavier\s+(logitech|microsoft|hp|dell|apple)\s*(.*?)(?:\s+sn:|\s+mo:|$)',
                 tl)
    if m:
        model_extra = m.group(2).strip()
        model_name = f"Clavier {model_extra}" if model_extra else "Clavier"
        return Equipment(category='peripherique', raw_text=t,
                         brand=m.group(1).capitalize(), model=model_name,
                         serial=serial)

    if re.match(r'^clavier\b', tl):
        return Equipment(category='peripherique', raw_text=t,
                         model='Clavier', serial=serial)

    m = re.match(r'^souris\s*(sans\s+fil\s*)?(logitech|microsoft|hp)?\s*(.*)', tl)
    if m and re.match(r'^souris\b', tl):
        brand = m.group(2).capitalize() if m.group(2) else None
        return Equipment(category='peripherique', raw_text=t, brand=brand,
                         model='Souris', serial=serial)

    m = re.match(r'^moniteur\s+(dell|lg|samsung|hp|asus|acer|benq)\s*(.*)', tl)
    if m:
        model_extra = m.group(2).strip()
        return Equipment(category='peripherique', raw_text=t,
                         brand=m.group(1).capitalize(),
                         model=f"Moniteur {model_extra}".strip(),
                         serial=serial)

    if re.match(r'^(?:moniteur|ecran)\b', tl):
        return Equipment(category='peripherique', raw_text=t,
                         model='Moniteur', serial=serial)

    # ─── Software (at root level) ───
    sw = [
        (r'^thunderbird\b', 'Thunderbird'),
        (r'^office\s*\d*\b', 'Microsoft Office'),
        (r'^excel\b', 'Excel'),
        (r'^word\b', 'Word'),
        (r'^chrome\b', 'Google Chrome'),
        (r'^firefox\b', 'Firefox'),
        (r'^outlook\b', 'Outlook'),
        (r'^whatsapp\b', 'WhatsApp'),
    ]
    for pat, name in sw:
        if re.match(pat, tl):
            return Equipment(category='logiciel', raw_text=t, model=name)

    m = re.match(r'^compte\s+(sfr|orange|gmail|google|outlook|free)\b', tl)
    if m:
        return Equipment(category='compte', raw_text=t,
                         model=f"Compte {m.group(1).capitalize()}")

    # ─── Lenovo / brand + serial pattern (e.g. "Lenovo sn:xxx") ───
    m = re.match(r'^(lenovo|hp|dell|asus|acer)\s+([\w-]+)(?:\s+sn:(\S+))?', tl)
    if m:
        brand = m.group(1).capitalize()
        model_or_detail = m.group(2)
        sn = m.group(3) or serial
        # If second word looks like a model name, use it
        if model_or_detail.lower().startswith('sn:'):
            return Equipment(category='uc', raw_text=t, brand=brand,
                             serial=sn)
        return Equipment(category='uc', raw_text=t, brand=brand,
                         model=model_or_detail, serial=sn)

    return None


def get_indent_level(line):
    tabs = 0
    spaces = 0
    for ch in line:
        if ch == '\t':
            tabs += 1
        elif ch == ' ':
            spaces += 1
        else:
            break
    if tabs > 0:
        return tabs
    if spaces >= 6:
        return 2
    if spaces >= 2:
        return 1
    return 0


def extract_equipment_from_note(raw_body):
    """Parse a note body and extract equipment with their details.

    Structure rules:
    - Level 0 lines are either equipment names or context headers (ad:, pb:, etc.)
    - Level 1 lines under equipment are details
    - Level 1 lines under context headers (ad:, pb:) might also be equipment
    - Level 2+ lines are always details of the nearest equipment above
    """
    lines = raw_body.split("\n")
    equipments = []
    current_equipment = None
    # Track whether we're in a "header context" (ad:, pb:, etc.)
    # where indented lines might still be equipment
    in_header_context = False

    for line in lines:
        if not line.strip():
            continue

        text = line.strip()
        if text.startswith('>') or text.startswith('{"Called"'):
            continue
        if re.match(r'^\+\d{10,}$', text):
            continue
        if re.match(r'^On \d+/\d+/\d+', text):
            break
        if re.match(r'^\d+ \w+\.? \d{4} \d+:\d+', text):
            break
        if text in ('--', '-- '):
            break

        level = get_indent_level(line)

        if level == 0:
            eq = _detect_equipment(line)
            if eq:
                current_equipment = eq
                equipments.append(current_equipment)
                in_header_context = False
            else:
                tl = text.lower()
                if tl.startswith('ad:') or tl.startswith('ad :'):
                    # AD line is a header, keep looking for equipment below
                    in_header_context = True
                elif tl.startswith('pb:') or tl.startswith('pb '):
                    in_header_context = True
                    current_equipment = None
                else:
                    current_equipment = None
                    in_header_context = False
        elif level == 1:
            # Try to detect equipment even at indent level 1
            # if we're in a header context OR no current equipment
            if in_header_context or current_equipment is None:
                eq = _detect_equipment(text)
                if eq:
                    current_equipment = eq
                    equipments.append(current_equipment)
                    in_header_context = False
                    continue
            # Otherwise it's a detail of current equipment
            if current_equipment:
                current_equipment.details.append(text)
        else:
            # Level 2+ is always a detail
            if current_equipment:
                current_equipment.details.append(text)

    return equipments


def extract_equipment_from_all_notes(notes):
    """Extract equipment from list of note dicts with 'raw' and 'date'."""
    results = []
    for note in notes:
        equipments = extract_equipment_from_note(note["raw"])
        if equipments:
            results.append({
                "date": note["date"],
                "subject": note["subject"],
                "equipments": equipments,
            })
    return results


def build_equipment_inventory(results):
    """Build deduplicated inventory grouped by category."""
    seen = {}
    for r in results:
        for eq in r["equipments"]:
            key = eq.unique_key
            if key not in seen:
                seen[key] = {"equipment": eq, "count": 0, "dates": []}
            seen[key]["count"] += 1
            seen[key]["dates"].append(r["date"])

    categories = {}
    for key, info in seen.items():
        cat = info["equipment"].category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(info)

    return categories
