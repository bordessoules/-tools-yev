"""
Modèles de données — Geekadomicile Email Timeline

Dataclasses typées pour les échanges client, pièces jointes et infos client.
Remplace les dictionnaires bruts pour une meilleure lisibilité et détection d'erreurs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AttachmentInfo:
    """Pièce jointe extraite d'un email."""
    filename: str
    saved_name: str
    content_type: str
    size: int
    saved_path: str = ""


@dataclass
class Exchange:
    """Un échange unique dans la timeline (email, appel, RDV, session temps…)."""
    date: Optional[datetime]
    type: str                              # ex: "call_incoming", "email_client"
    type_label: str                        # ex: "Appel entrant", "Email client"
    direction: str                         # "in", "out", "cal", "work"
    subject: str
    body: str                              # Corps nettoyé pour affichage
    from_addr: str = ""
    to_addr: str = ""
    sender_name: str = ""
    folder: str = ""
    amount: Optional[str] = None           # Montant extrait du sujet
    duration_display: Optional[str] = None
    equipments: list = field(default_factory=list)     # List[Equipment]
    attachments: list = field(default_factory=list)    # List[AttachmentInfo]

    # Champs internes (non affichés)
    date_str: str = ""
    full_body: str = ""


@dataclass
class Client:
    """Client Geekadomicile."""
    id: str
    name: str
    phones: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    address: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Client":
        """Crée un Client depuis un dict JSON."""
        return cls(
            id=d.get("id", "unknown"),
            name=d.get("name", ""),
            phones=d.get("phones", []),
            emails=d.get("emails", []),
            address=d.get("address", ""),
        )
