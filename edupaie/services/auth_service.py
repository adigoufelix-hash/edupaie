from edupaie.db.repositories import utilisateur_repository as repo
from edupaie.security import (
    hasher_pour_stockage,
    verifier_complexite,
    verifier_stocke,
)

_utilisateur_courant = None


def authentifier(login: str, mot_de_passe: str):
    """Retourne l'utilisateur connecté, ou None si identifiants invalides."""
    global _utilisateur_courant
    ligne = repo.get_by_login(login.strip())
    if ligne is None or not verifier_stocke(mot_de_passe, ligne["mot_de_passe"]):
        return None
    _utilisateur_courant = {
        "id": ligne["id"],
        "login": ligne["login"],
        "nom_complet": ligne["nom_complet"],
        "role": ligne["role"],
    }
    return _utilisateur_courant


def utilisateur_courant():
    return _utilisateur_courant


def deconnecter():
    global _utilisateur_courant
    _utilisateur_courant = None


def creer_utilisateur(login, nom_complet, mot_de_passe, role):
    erreurs = verifier_complexite(mot_de_passe)
    if erreurs:
        raise ValueError("Mot de passe invalide : " + ", ".join(erreurs))
    return repo.creer(login.strip(), nom_complet, hasher_pour_stockage(mot_de_passe), role)