import base64
import binascii
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from edupaie.services.paiement_service import ErreurMetier

PREFIXE = "EDUPAIE1"
ESSAI_JOURS = 30

# Clé publique de vérification des licences (64 caractères hexadécimaux).
# À remplir avec la valeur affichée par :  python -m outils.generer_cles
CLE_PUBLIQUE_HEX = "53755fc8240a4d25bd053179d80a0577965883e5651a9c9364211730a0523829"

# Coordonnées proposées dans l'écran Licence (laisse vide pour les masquer)
SUPPORT_WHATSAPP = "22899239162"   # numéro international sans « + », ex. "22890123456"
SUPPORT_EMAIL = "adigoufelix@gmail.com"      # ex. "contact@monentreprise.tg"

MACHINE_VALIDE = re.compile(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){3}")


class ErreurLicence(ErreurMetier):
    """Licence refusée : le message est affichable tel quel."""


@dataclass(frozen=True)
class LicenceLue:
    id: str
    ecole: str
    machine: str
    emise: str
    expire: date | None


def _fr(jour: date) -> str:
    return f"{jour:%d/%m/%Y}"


def _en_base64(octets: bytes) -> str:
    return base64.urlsafe_b64encode(octets).decode("ascii").rstrip("=")


def _depuis_base64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def construire_cle(payload: bytes, signature: bytes) -> str:
    return f"{PREFIXE}.{_en_base64(payload)}.{_en_base64(signature)}"


def lire_cle(texte) -> tuple[bytes, bytes]:
    """(contenu, signature) ; les espaces et retours à la ligne sont ignorés."""
    morceaux = "".join(str(texte or "").split()).split(".")
    if len(morceaux) != 3 or morceaux[0] != PREFIXE:
        raise ValueError("format de clé inconnu")
    try:
        return _depuis_base64(morceaux[1]), _depuis_base64(morceaux[2])
    except (binascii.Error, ValueError):
        raise ValueError("clé corrompue") from None


def normaliser_machine(texte) -> str:
    return str(texte or "").strip().upper()


def _guid_machine() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as cle:
            return str(winreg.QueryValueEx(cle, "MachineGuid")[0])
    except Exception:
        return f"mac-{uuid.getnode():012x}"


def identifiant_machine(guid=None) -> str:
    """Identifiant de l'ordinateur, du type 3F2A-91BC-07DE-44A1 (stable tant que
    Windows n'est pas réinstallé)."""
    brut = str(guid) if guid is not None else _guid_machine()
    empreinte = hashlib.sha256(f"edupaie|machine|{brut}".encode("utf-8")).hexdigest().upper()
    return "-".join(empreinte[i:i + 4] for i in range(0, 16, 4))


def analyser_licence(texte, cle_publique_hex, machine, reference: date) -> LicenceLue:
    """Vérifie la signature, l'ordinateur et la date ; lève ErreurLicence sinon."""
    if not cle_publique_hex:
        raise ErreurLicence("Cette copie d'EduPaie n'est pas configurée pour recevoir "
                            "des licences.")
    try:
        payload, signature = lire_cle(texte)
    except ValueError:
        raise ErreurLicence("Clé de licence illisible : copie-la en entier, sans la "
                            "modifier.") from None
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(cle_publique_hex)).verify(
            signature, payload)
    except (InvalidSignature, ValueError):
        raise ErreurLicence("Clé de licence invalide : elle n'a pas été émise par le "
                            "fournisseur d'EduPaie.") from None
    try:
        donnees = json.loads(payload.decode("utf-8"))
        expire = date.fromisoformat(donnees["expire"]) if donnees.get("expire") else None
        licence = LicenceLue(str(donnees["id"]), str(donnees["ecole"]),
                             normaliser_machine(donnees["machine"]), str(donnees["emise"]),
                             expire)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ErreurLicence("Clé de licence invalide.") from None
    if licence.machine != "*" and licence.machine != normaliser_machine(machine):
        raise ErreurLicence("Cette licence est liée à un autre ordinateur. Demande une "
                            "licence pour l'identifiant de cet ordinateur.")
    if licence.expire and reference > licence.expire:
        raise ErreurLicence(f"Licence expirée le {_fr(licence.expire)}.")
    return licence