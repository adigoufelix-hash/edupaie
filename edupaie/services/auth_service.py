import sqlite3

from edupaie.permissions import ROLES, a_permission
from edupaie.security import (
    doit_etre_rehache,
    hasher_pour_stockage,
    verifier_complexite,
    verifier_stocke,
)
from edupaie.services.paiement_service import ErreurMetier

MAX_ECHECS = 5


class AuthService:
    def __init__(self, repo):
        self.repo = repo
        self.utilisateur = None  # dict de l'utilisateur connecté
        self._echecs = {}

    # --- Droits -----------------------------------------------------------
    def peut(self, permission: str) -> bool:
        return self.utilisateur is not None and a_permission(
            self.utilisateur["role"], permission)

    def _exiger_admin(self):
        if not self.peut("utilisateur.gerer"):
            raise ErreurMetier("Action réservée à l'administrateur.")

    # --- Gestion des utilisateurs (admin) -------------------------------------
    def lister_utilisateurs(self):
        self._exiger_admin()
        return self.repo.lister()

    def reinitialiser_mot_de_passe(self, utilisateur_id: int, nouveau: str) -> None:
        self._exiger_admin()
        erreurs = verifier_complexite(nouveau)
        if erreurs:
            raise ErreurMetier("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        self.repo.maj_mot_de_passe(utilisateur_id, hasher_pour_stockage(nouveau))

    def supprimer_utilisateur(self, utilisateur_id: int) -> None:
        self._exiger_admin()
        if utilisateur_id == self.utilisateur["id"]:
            raise ErreurMetier("Vous ne pouvez pas supprimer votre propre compte.")
        cible = self.repo.get(utilisateur_id)
        if cible is None:
            return
        if cible["role"] == "admin" and self.repo.compter_admins() <= 1:
            raise ErreurMetier("Il doit rester au moins un administrateur.")
        self.repo.supprimer(utilisateur_id)

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
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise ErreurMetier("Ce login existe déjà.")
            raise ErreurMetier(f"Enregistrement impossible : {e}")

    # --- Connexion ----------------------------------------------------------------
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
        if doit_etre_rehache(ligne["mot_de_passe"]):
            self.repo.maj_mot_de_passe(ligne["id"], hasher_pour_stockage(mot_de_passe))
        self.utilisateur = {
            "id": ligne["id"],
            "login": ligne["login"],
            "nom_complet": ligne["nom_complet"],
            "role": ligne["role"],
        }
        return self.utilisateur

    def deconnecter(self) -> None:
        self.utilisateur = None

    def changer_mon_mot_de_passe(self, ancien: str, nouveau: str) -> None:
        if self.utilisateur is None:
            raise ErreurMetier("Aucun utilisateur connecté.")
        ligne = self.repo.get(self.utilisateur["id"])
        if ligne is None or not verifier_stocke(ancien, ligne["mot_de_passe"]):
            raise ErreurMetier("L'ancien mot de passe est incorrect.")
        if nouveau == ancien:
            raise ErreurMetier("Le nouveau mot de passe doit être différent de l'ancien.")
        erreurs = verifier_complexite(nouveau)
        if erreurs:
            raise ErreurMetier("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        self.repo.maj_mot_de_passe(ligne["id"], hasher_pour_stockage(nouveau))