"""
Gestion des pièces jointes — Geekadomicile Email Timeline

Extraction, sauvegarde sur disque, détection de type et formatage.
"""

import hashlib
import os
import re

from fetch_emails import decode_mime_header
from config import ATTACHMENTS_DIR, HASH_PREFIX_LEN, IMAGE_EXTENSIONS


def extract_attachments(msg, client_id):
    """Extrait les pièces jointes d'un email MIME et les sauvegarde.

    Args:
        msg: email.message.Message parsé
        client_id: identifiant client pour le dossier de stockage

    Returns:
        list de dicts {filename, size, content_type, saved_path, saved_name}
    """
    attachments = []
    att_dir = os.path.join(ATTACHMENTS_DIR, client_id)

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition and "inline" not in content_disposition:
            continue

        ct = part.get_content_type()
        if ct in ("text/plain", "text/html") and "attachment" not in content_disposition:
            continue

        filename = part.get_filename()
        if not filename:
            continue
        filename = decode_mime_header(filename)
        filename = re.sub(r'[\r\n\t]+', ' ', filename).strip()

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        size = len(payload)

        # Sauvegarde sur disque avec hash-prefix anti-collision
        os.makedirs(att_dir, exist_ok=True)
        safe_name = re.sub(r'[\r\n\t]', '', filename)
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
        safe_name = safe_name.strip()
        prefix = hashlib.md5(payload[:1024]).hexdigest()[:HASH_PREFIX_LEN]
        saved_name = f"{prefix}_{safe_name}"
        saved_path = os.path.join(att_dir, saved_name)

        if not os.path.exists(saved_path):
            with open(saved_path, "wb") as f:
                f.write(payload)

        attachments.append({
            "filename": filename,
            "size": size,
            "content_type": ct,
            "saved_path": saved_path,
            "saved_name": saved_name,
        })

    return attachments


def att_icon(content_type, filename):
    """Retourne une icône HTML entity selon le type de fichier."""
    fn = (filename or "").lower()
    if is_image(filename, content_type):
        return '&#128247;'  # 📷
    if fn.endswith('.pdf') or content_type == 'application/pdf':
        return '&#128196;'  # 📄
    if fn.endswith(('.doc', '.docx', '.odt')):
        return '&#128196;'  # 📄
    if fn.endswith(('.xls', '.xlsx', '.ods', '.csv')):
        return '&#128202;'  # 📊
    return '&#128206;'      # 📎


def format_size(size):
    """Formate une taille en octets en format lisible (Ko, Mo)."""
    if size < 1024:
        return f"{size} o"
    if size < 1024 * 1024:
        return f"{size // 1024} Ko"
    return f"{size / (1024 * 1024):.1f} Mo"


def is_image(filename, content_type):
    """Détecte si un fichier est une image (par extension ou content-type)."""
    fn = (filename or "").lower()
    return fn.endswith(IMAGE_EXTENSIONS) or content_type.startswith('image/')
