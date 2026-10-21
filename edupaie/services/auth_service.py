from edupaie.security import (
    hasher_pour_stockage,
    verifier_complexite,
    verifier_stocke,
)


class AuthService:
    def __init__(self, repo):
        self.repo = repo
        self.utilisateur = None  # dict de l'utilisateur connecté

    def aucun_utilisateur(self) -> bool:
        return self.repo.compter() == 0

    def authentifier(self, login: str, mot_de_passe: str):
        ligne = self.repo.get_by_login(login.strip())
        if ligne is None or not verifier_stocke(mot_de_passe, ligne["mot_de_passe"]):
            return None
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
        erreurs = verifier_complexite(mot_de_passe)
        if erreurs:
            raise ValueError("Mot de passe invalide : " + ", ".join(erreurs) + ".")
        return self.repo.creer(
            login.strip(), nom_complet.strip(), hasher_pour_stockage(mot_de_passe), role
        )