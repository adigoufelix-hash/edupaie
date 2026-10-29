from edupaie.services import couleurs
from edupaie.services.ecole import ParametresEcole, definir
from edupaie.services.paiement_service import ErreurMetier

GARDER = object()  # « ne pas toucher à la valeur existante »
SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"
TAILLE_MAX_LOGO = 1_000_000  # octets


class EcoleService:
    def __init__(self, repo, auth=None):
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits

    def peut_modifier(self) -> bool:
        return self.auth is None or self.auth.peut("ecole.gerer")

    def lire(self) -> ParametresEcole:
        ligne = self.repo.lire()
        if ligne is None:
            return ParametresEcole()
        return ParametresEcole(
            ligne["nom"] or "", ligne["adresse"] or "", ligne["telephone"] or "",
            ligne["email"] or "", bytes(ligne["logo"]) if ligne["logo"] else None,
            ligne["couleur"] or "")

    @staticmethod
    def _texte(valeur, maximum, nom) -> str:
        valeur = " ".join(str(valeur or "").split())
        if len(valeur) > maximum:
            raise ErreurMetier(f"{nom} : {maximum} caractères au maximum.")
        return valeur

    def enregistrer(self, nom, adresse="", telephone="", email="",
                    logo=GARDER, couleur=GARDER) -> None:
        """logo : GARDER, None (retirer) ou une image PNG.
        couleur : GARDER, "" (couleur d'origine) ou un code #RRGGBB."""
        if not self.peut_modifier():
            raise ErreurMetier(
                "Seul un administrateur peut modifier les paramètres de l'école.")
        nom = self._texte(nom, 80, "Le nom de l'école")
        if not nom:
            raise ErreurMetier("Le nom de l'école est obligatoire.")
        adresse = self._texte(adresse, 120, "L'adresse")
        telephone = self._texte(telephone, 40, "Le téléphone")
        email = self._texte(email, 80, "L'e-mail")
        if email and "@" not in email:
            raise ErreurMetier("L'adresse e-mail n'est pas valide.")
        actuel = self.repo.lire()
        if logo is GARDER:
            logo = bytes(actuel["logo"]) if actuel and actuel["logo"] else None
        elif logo is not None:
            if not isinstance(logo, (bytes, bytearray)) or not bytes(logo).startswith(SIGNATURE_PNG):
                raise ErreurMetier("Le logo doit être une image PNG.")
            if len(logo) > TAILLE_MAX_LOGO:
                raise ErreurMetier("Le logo est trop volumineux (1 Mo au maximum).")
            logo = bytes(logo)
        if couleur is GARDER:
            couleur = (actuel["couleur"] or "") if actuel else ""
        else:
            couleur = str(couleur or "").strip()
            if couleur:
                couleur = couleurs.normaliser(couleur)
                if couleur is None:
                    raise ErreurMetier(
                        "Couleur invalide : utilise le format #RRGGBB (ex. #0F766E).")
        self.repo.enregistrer(nom, adresse, telephone, email, logo, couleur)
        definir(self.lire())  # les PDF suivants utilisent aussitôt les nouvelles valeurs