from dataclasses import dataclass


@dataclass(frozen=True)
class ParametresEcole:
    nom: str = ""
    adresse: str = ""
    telephone: str = ""
    email: str = ""
    logo: bytes | None = None  # image PNG

    @property
    def nom_affiche(self) -> str:
        return self.nom or "EduPaie"

    @property
    def coordonnees(self) -> str:
        return " - ".join(p for p in (self.adresse, self.telephone, self.email) if p)


_courant = ParametresEcole()


def courant() -> ParametresEcole:
    """Paramètres de l'école utilisés par défaut dans les PDF."""
    return _courant


def definir(parametres: ParametresEcole) -> None:
    global _courant
    _courant = parametres