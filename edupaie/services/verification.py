import hmac
import re
from hashlib import sha256

_cle = None
_NUMERO = re.compile(r"REC-(\d{4})-(\d+)")


def definir_cle(cle) -> None:
    """Clé propre à l'installation (créée au premier lancement, conservée dans la base)."""
    global _cle
    _cle = cle or None


def calculer_code(cle, numero, montant, date_paiement, mode, eleve_id) -> str:
    """Code de 10 caractères lié au numéro, au montant, à la date, au mode et à l'élève.
    Il ne dépend pas du solde, qui peut changer légitimement."""
    message = "|".join([str(numero), str(int(montant)), str(date_paiement),
                        str(mode), str(eleve_id)])
    return hmac.new(cle.encode("utf-8"), message.encode("utf-8"), sha256
                    ).hexdigest()[:10].upper()


def formater_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}"


def code_pour(paiement):
    if not _cle or not paiement.numero_recu:
        return None
    return calculer_code(_cle, paiement.numero_recu, paiement.montant,
                         paiement.date_paiement, paiement.mode, paiement.eleve_id)


def contenu_qr(paiement):
    """Texte du QR : lettres et chiffres seulement (fiable avec une douchette)."""
    code = code_pour(paiement)
    m = _NUMERO.fullmatch(paiement.numero_recu or "")
    if code is None or m is None:
        return None
    return f"EDUPAIE{m.group(1)}{m.group(2)}{code}"


def code_affiche(paiement) -> str:
    code = code_pour(paiement)
    return "Code : " + formater_code(code) if code else ""


def lire_saisie(saisie):
    """(numéro, code) depuis le contenu d'un QR ou une saisie à la main ; (None, None)
    si illisible. Le code est None s'il n'est pas fourni."""
    brut = str(saisie or "").strip().upper()
    compact = re.sub(r"\s+", "", brut)
    m = re.fullmatch(r"EDUPAIE(\d{4})(\d+?)([0-9A-F]{10})", compact)
    if m:
        return f"REC-{m.group(1)}-{m.group(2)}", m.group(3)
    jetons = brut.split()
    if not jetons or not _NUMERO.fullmatch(jetons[0]):
        return None, None
    code = re.sub(r"[^0-9A-F]", "", "".join(jetons[1:]))
    return jetons[0], code or None