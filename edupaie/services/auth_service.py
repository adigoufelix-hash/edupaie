import sqlite3

from edupaie.permissions import ROLES  # adapte le nom à ton fichier
from edupaie.security import (
    hasher_pour_stockage,
    verifier_complexite,
    verifier_stocke,
)
from edupaie.services.paiement_service import ErreurMetier

MAX_ECHECS = 5


class AuthService:
    def __init__(self, repo):
        self.repo = repo
        self.utilisateur = None
        self._echecs = {}

    def aucun_utilisateur(self) -> bool:
        return self.repo.compter() == 0

    def authentifier(self, login: str, mot_de_passe: str):
        login = login.strip().lower()
        if self._echecs.get(login, 0) >= MAX_ECHECS:
            raise ErreurMetier(
                "Trop de tentatives. Redémarrez l'application ou contactez l'administrateur.")
        ligne = self.repo.get_by_login(login)
        if ligne is None or not verifier_stocke(mot_de_passe, ligne["mot_de_passe"]):
            self._echecs[login] = self._echecs.get(login, 0) + 1
            return None
        self._echecs.pop(login, None)
        self.utilisateur = {
            "id": ligne["id"],
            "login": ligne["login"],
            "nom_complet": ligne["nom_complet"],
            "role": ligne["role"],
        }
        return self.utilisateur

    def deconnecter(self) -> None:
        self.utilisateur = None

    def creer_utilisateur(self, login, nom_complet, mot_de_passe, role) -> int:
        premier = self.aucun_utilisateur()
        if not premier and (self.utilisateur is None or self.utilisateur["role"] != "admin"):
            raise ErreurMetier("Seul un administrateur peut créer un compte.")
        if premier:
            role = "admin"  # le tout premier compte est administrateur
        login = login.strip().lower()
        if not login or not nom_complet.strip():
            raise ErreurMetier("Le login et le nom complet sont obligatoires.")
        if role not in ROLES:
            raise ErreurMetier("Rôle inconnu.")
        erreurs = verifier_complexite(mot_de_passe)
        if erreurs:
            raise ErreurMetier("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        try:
            return self.repo.creer(
                login, nom_complet.strip(), hasher_pour_stockage(mot_de_passe), role)
        except sqlite3.IntegrityError:
            raise ErreurMetier("Ce login existe déjà.")