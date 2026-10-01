import sqlite3

from edupaie.models.entities import Eleve
from edupaie.services.paiement_service import ErreurMetier


class EleveService:
    def __init__(self, eleve_repo):
        self.eleves = eleve_repo

    def lister(self, recherche: str = "", classe: str | None = None):
        return self.eleves.lister(recherche.strip(), classe or None)

    def classes(self):
        return self.eleves.classes()

    def enregistrer(self, eleve_id, nom, prenom, classe, annee, total_du) -> int:
        nom, prenom, classe, annee = (v.strip() for v in (nom, prenom, classe, annee))
        if not all((nom, prenom, classe, annee)):
            raise ErreurMetier("Tous les champs sont obligatoires.")
        try:
            total = int("".join(str(total_du).split()))
        except ValueError:
            raise ErreurMetier("Le total des frais doit être un nombre entier.") from None
        if total < 0:
            raise ErreurMetier("Le total des frais ne peut pas être négatif.")
        eleve = Eleve(eleve_id, nom, prenom, classe, annee, total)
        if eleve_id is None:
            return self.eleves.ajouter(eleve)
        self.eleves.modifier(eleve)
        return eleve_id

    def supprimer(self, eleve_id: int) -> None:
        try:
            self.eleves.supprimer(eleve_id)
        except sqlite3.IntegrityError:
            raise ErreurMetier(
                "Suppression impossible : cet élève a des paiements enregistrés."
            ) from None