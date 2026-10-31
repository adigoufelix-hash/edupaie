from dataclasses import dataclass

from edupaie.services import couleurs


@dataclass(frozen=True)
class ParametresEcole:
    nom: str = ""
    adresse: str = ""
    telephone: str = ""
    email: str = ""
    logo: bytes | None = None  # image PNG
    couleur: str = ""          # couleur principale de l'école ("" = couleur d'origine)
    boite_postale: str = ""    # ex. « BP 1234 »

    @property
    def nom_affiche(self) -> str:
        return self.nom or "EduPaie"

    @property
    def ligne_adresse(self) -> str:
        return " - ".join(p for p in (self.adresse, self.boite_postale) if p)

    @property
    def ligne_contact(self) -> str:
        return " - ".join(p for p in (self.telephone, self.email) if p)

    @property
    def coordonnees(self) -> str:
        return " - ".join(p for p in (self.ligne_adresse, self.ligne_contact) if p)

    @property
    def couleur_principale(self) -> tuple:
        return couleurs.principale_rgb(self.couleur)

    @property
    def couleur_sombre(self) -> tuple:
        return couleurs.sombre_rgb(self.couleur)


_courant = ParametresEcole()


def courant() -> ParametresEcole:
    """Paramètres de l'école utilisés par défaut dans les PDF et l'application."""
    return _courant


def definir(parametres: ParametresEcole) -> None:
    global _courant
    _courant = parametres