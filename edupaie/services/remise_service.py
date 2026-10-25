from datetime import datetime

from edupaie.services.paiement_service import ErreurMetier

TYPES = ("montant", "pourcentage")


class RemiseService:
    def __init__(self, remise_repo, eleve_repo, paiement_repo, auth=None):
        self.remises = remise_repo
        self.eleves = eleve_repo
        self.paiements = paiement_repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits

    def peut_gerer(self) -> bool:
        return self.auth is None or self.auth.peut("remise.gerer")

    def _exiger_droit(self):
        if not self.peut_gerer():
            raise ErreurMetier("Seul un administrateur peut gérer les remises.")

    def _auteur(self):
        if self.auth is not None and self.auth.utilisateur is not None:
            return self.auth.utilisateur["nom_complet"]
        return None

    @staticmethod
    def _entier(valeur):
        try:
            return int("".join(str(valeur).split()))
        except ValueError:
            return None

    @staticmethod
    def _valider_motif(motif) -> str:
        motif = str(motif).strip()
        if len(motif) < 5:
            raise ErreurMetier("Le motif est obligatoire (5 caractères minimum).")
        return motif

    def lister(self, eleve_id: int):
        return self.remises.lister_par_eleve(eleve_id)

    def montant_effectif(self, eleve_id, type_, valeur):
        """Aperçu du montant de la remise ; None si la saisie est invalide."""
        eleve = self.eleves.get(eleve_id)
        v = self._entier(valeur)
        if eleve is None or v is None or v <= 0:
            return None
        if type_ == "pourcentage":
            return eleve.total_du * v // 100 if v <= 100 else None
        if type_ == "montant":
            return v
        return None

    def accorder(self, eleve_id, type_, valeur, motif) -> int:
        self._exiger_droit()
        if type_ not in TYPES:
            raise ErreurMetier("Type de remise invalide.")
        motif = self._valider_motif(motif)
        v = self._entier(valeur)
        if v is None or v <= 0:
            raise ErreurMetier("La valeur doit être un nombre entier supérieur à 0.")
        if type_ == "pourcentage" and v > 100:
            raise ErreurMetier("Le pourcentage ne peut pas dépasser 100.")
        eleve = self.eleves.get(eleve_id)
        if eleve is None:
            raise ErreurMetier("Élève introuvable.")
        montant = self.montant_effectif(eleve_id, type_, v)
        if not montant:
            raise ErreurMetier("Cette remise est nulle : augmente la valeur.")
        solde = (eleve.total_du - self.paiements.total_remises(eleve_id)
                 - self.paiements.total_paye(eleve_id))
        if montant > solde:
            raise ErreurMetier(
                f"La remise ({montant}) dépasse le solde restant ({solde}).")
        quand = datetime.now().isoformat(timespec="seconds")
        remise_id = self.remises.ajouter(
            eleve_id, type_, v, montant, motif, self._auteur(), quand)
        self.paiements.recalculer_soldes(eleve_id)
        return remise_id

    def annuler(self, remise_id: int, motif) -> None:
        self._exiger_droit()
        motif = self._valider_motif(motif)
        remise = self.remises.obtenir(remise_id)
        if remise is None:
            raise ErreurMetier("Remise introuvable.")
        if remise["annule"]:
            raise ErreurMetier("Cette remise est déjà annulée.")
        quand = datetime.now().isoformat(timespec="seconds")
        self.remises.annuler(remise_id, motif, self._auteur(), quand)
        self.paiements.recalculer_soldes(remise["eleve_id"])