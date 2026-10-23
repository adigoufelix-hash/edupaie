"""Hachage des mots de passe et règles de complexité (bibliothèque standard uniquement)."""
import hashlib
import hmac
import os

ITERATIONS = 600_000
LONGUEUR_MIN = 8


def generer_sel() -> str:
    return os.urandom(16).hex()


def hasher_mot_de_passe(mot_de_passe: str, sel: str, iterations: int = ITERATIONS) -> str:
    cle = hashlib.pbkdf2_hmac(
        "sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), iterations
    )
    return cle.hex()


def verifier_mot_de_passe(mot_de_passe: str, sel: str, hash_attendu: str) -> bool:
    return hmac.compare_digest(hasher_mot_de_passe(mot_de_passe, sel), hash_attendu)


def verifier_complexite(mot_de_passe: str) -> list[str]:
    """Retourne la liste des règles non respectées (liste vide = mot de passe accepté)."""
    erreurs = []
    if len(mot_de_passe) < LONGUEUR_MIN:
        erreurs.append(f"au moins {LONGUEUR_MIN} caractères")
    if not any(c.isalpha() for c in mot_de_passe):
        erreurs.append("au moins une lettre")
    if not any(c.isdigit() for c in mot_de_passe):
        erreurs.append("au moins un chiffre")
    return erreurs

def hasher_pour_stockage(mot_de_passe: str) -> str:
    """Retourne la valeur à stocker : iterations$sel$hash."""
    sel = generer_sel()
    return f"{ITERATIONS}${sel}${hasher_mot_de_passe(mot_de_passe, sel)}"


ITERATIONS = 600_000

def verifier_stocke(mot_de_passe: str, stocke: str) -> bool:
    """Vérifie un mot de passe contre la valeur stockée en base."""
    try:
        iterations, sel, hash_attendu = stocke.split("$")
        calcule = hasher_mot_de_passe(mot_de_passe, sel, int(iterations))
        return hmac.compare_digest(calcule.encode(), hash_attendu.encode())
    except (ValueError, TypeError):
        return False
    
def doit_etre_rehache(stocke: str) -> bool:
    try:
        return int(stocke.split("$")[0]) < ITERATIONS
    except ValueError:
        return True