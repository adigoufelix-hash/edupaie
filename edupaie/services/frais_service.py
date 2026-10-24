import sqlite3

from edupaie.services.paiement_service import ErreurMetier


class FraisService:
    def __init__(self, repo, auth=None):
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits

    # --- Lecture : ouverte à tous (utilisée par le formulaire élève) -------------
    def classes(self) -> list[str]:
        return self.repo.classes()

    def detail(self, classe: str, annee: str):
        return self.repo.lister(classe.strip(), annee.strip())

    def total(self, classe: str, annee: str) -> int:
        return self.repo.total(classe.strip(), annee.strip())

    # --- Écriture : réservée à l'administrateur -------------------------------------
    def _exiger_droit(self):
        if self.auth is not None and not self.auth.peut("frais.gerer"):
            raise ErreurMetier("Action réservée à l'administrateur.")

    @staticmethod
    def _valider_classe(classe, annee):
        classe, annee = str(classe).strip(), str(annee).strip()
        if not classe:
            raise ErreurMetier("La classe est obligatoire.")
        if not annee:
            raise ErreurMetier("L'année scolaire est obligatoire.")
        return classe, annee

    @staticmethod
    def _valider_ligne(libelle, montant):
        libelle = str(libelle).strip()
        if not libelle:
            raise ErreurMetier("Le libellé est obligatoire.")
        try:
            montant = int("".join(str(montant).split()))
        except ValueError:
            raise ErreurMetier("Le montant doit être un nombre entier.") from None
        if montant <= 0:
            raise ErreurMetier("Le montant doit être supérieur à 0.")
        return libelle, montant

    def ajouter_ligne(self, classe, annee, libelle, montant) -> int:
        self._exiger_droit()
        classe, annee = self._valider_classe(classe, annee)
        libelle, montant = self._valider_ligne(libelle, montant)
        try:
            return self.repo.ajouter(classe, annee, libelle, montant)
        except sqlite3.IntegrityError:
            raise ErreurMetier("Cette ligne existe déjà pour cette classe.") from None

    def modifier_ligne(self, frais_id: int, libelle, montant) -> None:
        self._exiger_droit()
        libelle, montant = self._valider_ligne(libelle, montant)
        try:
            self.repo.modifier(frais_id, libelle, montant)
        except sqlite3.IntegrityError:
            raise ErreurMetier("Une autre ligne porte déjà ce libellé.") from None

    def supprimer_ligne(self, frais_id: int) -> None:
        self._exiger_droit()
        self.repo.supprimer(frais_id)

    def copier(self, classe_source, annee, classe_cible) -> int:
        """Copie les lignes d'une classe vers une autre (sans écraser l'existant)."""
        self._exiger_droit()
        classe_source, annee = self._valider_classe(classe_source, annee)
        classe_cible, _ = self._valider_classe(classe_cible, annee)
        if classe_cible == classe_source:
            raise ErreurMetier("Choisis une autre classe que la classe d'origine.")
        lignes = self.repo.lister(classe_source, annee)
        if not lignes:
            raise ErreurMetier("Cette classe n'a aucun frais à copier.")
        deja = {l["libelle"].lower() for l in self.repo.lister(classe_cible, annee)}
        copiees = 0
        for ligne in lignes:
            if ligne["libelle"].lower() not in deja:
                self.repo.ajouter(classe_cible, annee, ligne["libelle"], ligne["montant"])
                copiees += 1
        return copiees