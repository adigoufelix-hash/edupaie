import secrets
import sqlite3
from datetime import datetime

from edupaie.permissions import ROLES, a_permission
from edupaie.security import (
    doit_etre_rehache,
    generer_sel,
    hasher_mot_de_passe,
    hasher_pour_stockage,
    verifier_complexite,
    verifier_stocke,
)
from edupaie.services.paiement_service import ErreurMetier

MAX_ECHECS = 5

# Codes de secours : sans I, L, O, 0 et 1 (faciles à confondre à la lecture)
ALPHABET_CODES = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
NB_CODES = 8
LONGUEUR_CODE = 10
ITERATIONS_CODE = 100_000  # codes longs et aléatoires : moins de calcul qu'un mot de passe


def normaliser_code(texte) -> str:
    return "".join(c for c in str(texte or "").upper() if c.isalnum())


def formater_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}"


def _hacher_code(code: str) -> str:
    sel = generer_sel()
    return f"{ITERATIONS_CODE}${sel}${hasher_mot_de_passe(code, sel, ITERATIONS_CODE)}"


class AuthService:
    def __init__(self, repo, codes=None):
        self.repo = repo
        self.codes = codes  # dépôt des codes de secours (None dans certains tests)
        self.utilisateur = None  # dict de l'utilisateur connecté
        self._echecs = {}

    # --- Droits --------------------------------------------------------------------
    def peut(self, permission: str) -> bool:
        return self.utilisateur is not None and a_permission(
            self.utilisateur["role"], permission)

    def _exiger_admin(self):
        if not self.peut("utilisateur.gerer"):
            raise ErreurMetier("Action réservée à l'administrateur.")

    # --- Gestion des comptes (admin) ------------------------------------------------
    def lister_utilisateurs(self):
        self._exiger_admin()
        return self.repo.lister()

    def nombre_admins(self) -> int:
        return self.repo.compter_admins()

    def reinitialiser_mot_de_passe(self, utilisateur_id: int, nouveau: str) -> None:
        """Mot de passe temporaire : l'utilisateur devra en choisir un autre."""
        self._exiger_admin()
        erreurs = verifier_complexite(nouveau)
        if erreurs:
            raise ErreurMetier("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        self.repo.maj_mot_de_passe(
            utilisateur_id, hasher_pour_stockage(nouveau), doit_changer=True)

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
                login, nom_complet.strip(), hasher_pour_stockage(mot_de_passe), role,
                doit_changer=not premier)  # mot de passe temporaire, sauf pour le premier admin
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise ErreurMetier("Ce login existe déjà.") from None
            raise ErreurMetier(f"Enregistrement impossible : {e}") from None

    # --- Connexion -----------------------------------------------------------------
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
            "doit_changer_mdp": bool(ligne["doit_changer_mdp"]),
        }
        return self.utilisateur

    def deconnecter(self) -> None:
        self.utilisateur = None

    # --- Changement de mot de passe ----------------------------------------------------
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
        self.repo.maj_mot_de_passe(
            ligne["id"], hasher_pour_stockage(nouveau), doit_changer=False)
        self.utilisateur["doit_changer_mdp"] = False

    def definir_mon_mot_de_passe(self, nouveau: str) -> None:
        """Changement obligatoire après un mot de passe temporaire (pas d'ancien à saisir :
        l'utilisateur vient de le taper pour se connecter)."""
        if self.utilisateur is None:
            raise ErreurMetier("Aucun utilisateur connecté.")
        ligne = self.repo.get(self.utilisateur["id"])
        if ligne is None or not ligne["doit_changer_mdp"]:
            raise ErreurMetier("Aucun changement de mot de passe n'est demandé pour ce compte.")
        erreurs = verifier_complexite(nouveau)
        if erreurs:
            raise ErreurMetier("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        if verifier_stocke(nouveau, ligne["mot_de_passe"]):
            raise ErreurMetier("Choisis un mot de passe différent du mot de passe temporaire.")
        self.repo.maj_mot_de_passe(
            ligne["id"], hasher_pour_stockage(nouveau), doit_changer=False)
        self.utilisateur["doit_changer_mdp"] = False

    # --- Codes de secours (administrateurs) ---------------------------------------------
    def generer_codes_secours(self, mot_de_passe: str) -> list[str]:
        """Génère 8 nouveaux codes (les anciens sont invalidés). Affichés une seule fois."""
        if self.codes is None:
            raise ErreurMetier("Les codes de secours ne sont pas disponibles.")
        if self.utilisateur is None or self.utilisateur["role"] != "admin":
            raise ErreurMetier("Les codes de secours sont réservés aux administrateurs.")
        ligne = self.repo.get(self.utilisateur["id"])
        if ligne is None or not verifier_stocke(mot_de_passe, ligne["mot_de_passe"]):
            raise ErreurMetier("Mot de passe incorrect.")
        codes = set()
        while len(codes) < NB_CODES:
            codes.add("".join(secrets.choice(ALPHABET_CODES) for _ in range(LONGUEUR_CODE)))
        codes = sorted(codes)
        self.codes.remplacer(ligne["id"], [_hacher_code(c) for c in codes])
        return [formater_code(c) for c in codes]

    def codes_secours_restants(self) -> int:
        if self.codes is None or self.utilisateur is None or self.utilisateur["role"] != "admin":
            return 0
        return self.codes.compter_restants(self.utilisateur["id"])

    def reinitialiser_avec_code(self, login: str, code: str, nouveau: str) -> int:
        """Récupère un compte administrateur avec un code de secours (usage unique).
        Retourne le nombre de codes restants."""
        login = str(login).strip().lower()
        cle = f"recuperation:{login}"
        if self._echecs.get(cle, 0) >= MAX_ECHECS:
            raise ErreurMetier(
                "Trop de tentatives. Redémarre l'application ou demande l'aide de ton fournisseur.")
        erreurs = verifier_complexite(nouveau)  # avant tout : un mot de passe refusé ne consomme pas le code
        if erreurs:
            raise ErreurMetier("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        ligne = self.repo.get_by_login(login)
        code_id = None
        if ligne is not None and self.codes is not None:
            saisi = normaliser_code(code)
            for candidat in self.codes.non_utilises(ligne["id"]):
                if verifier_stocke(saisi, candidat["empreinte"]):
                    code_id = candidat["id"]
                    break
        if code_id is None:
            self._echecs[cle] = self._echecs.get(cle, 0) + 1
            raise ErreurMetier("Identifiant ou code de secours incorrect.")
        self.codes.marquer_utilise(code_id, datetime.now().isoformat(timespec="seconds"))
        self.repo.maj_mot_de_passe(
            ligne["id"], hasher_pour_stockage(nouveau), doit_changer=False)
        self._echecs.pop(cle, None)
        self._echecs.pop(login, None)  # le compte est débloqué
        return self.codes.compter_restants(ligne["id"])