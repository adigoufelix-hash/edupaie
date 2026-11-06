import re

LONGUEUR_MAX = 40
MIN_CARACTERES = 4


def normaliser(texte) -> str:
    """Forme comparable d'un numéro de transaction : majuscules, lettres et chiffres seulement
    (« mp-2611.0001 » et « MP2611 0001 » sont le même numéro)."""
    return re.sub(r"[^A-Z0-9]", "", str(texte or "").upper())


def nettoyer(texte):
    """Numéro saisi par le caissier : une seule ligne, sans espaces superflus.
    Retourne None s'il est vide ; lève ValueError (message affichable) s'il est invalide."""
    propre = " ".join(str(texte or "").split())
    if not propre:
        return None
    if len(propre) > LONGUEUR_MAX:
        raise ValueError(f"Le numéro de transaction est trop long ({LONGUEUR_MAX} caractères "
                         "au maximum).")
    if not re.fullmatch(r"[A-Za-z0-9 ._/\-]+", propre):
        raise ValueError("Le numéro de transaction ne peut contenir que des lettres, des "
                         "chiffres et les signes . - _ /")
    if len(normaliser(propre)) < MIN_CARACTERES:
        raise ValueError("Le numéro de transaction est trop court : recopie-le en entier "
                         "depuis le SMS de confirmation.")
    return propre