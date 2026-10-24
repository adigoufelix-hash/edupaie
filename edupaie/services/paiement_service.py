from dataclasses import dataclass
from datetime import date, datetime

from edupaie.models.entities import Paiement

MODES = ("especes", "cheque", "virement", "mobile_money")
STATUT_SOLDE = "Soldé"
STATUT_PARTIEL = "Partiellement payé"
STATUT_NON_PAYE = "Non payé"


class ErreurMetier(Exception):
    """Erreur de validation, message affichable tel quel à l'utilisateur."""


@dataclass
class Situation:
    total_du: int
    total_paye: int
    solde: int
    statut: str


def calculer_statut(total_du: int, total_paye: int) -> str:
    if total_paye >= total_du:
        return STATUT_SOLDE
    if total_paye == 0:
        return STATUT_NON_PAYE
    return STATUT_PARTIEL


class PaiementService:
    def __init__(self, eleve_repo, paiement_repo, auth=None):
        self.eleves = eleve_repo
        self.paiements = paiement_repo
        self.auth = auth  # utilisateur connecté (None dans les tests)

    def situation(self, eleve_id: int) -> Situation:
        eleve = self.eleves.get(eleve_id)
        if eleve is None:
            raise ErreurMetier("Élève introuvable.")
        paye = self.paiements.total_paye(eleve_id)
        return Situation(eleve.total_du, paye, eleve.total_du - paye,
                         calculer_statut(eleve.total_du, paye))

    def tableau_de_bord(self) -> dict:
        """Chiffres clés pour le tableau de bord."""
        situations = self.situations()
        return {
            "nb_eleves": len(situations),
            "total_encaisse": sum(s.total_paye for _, s in situations),
            "total_restant": sum(s.solde for _, s in situations),
            "nb_non_soldes": sum(1 for _, s in situations if s.solde > 0),
            "nb_soldes": sum(1 for _, s in situations if s.statut == STATUT_SOLDE),
            "nb_partiels": sum(1 for _, s in situations if s.statut == STATUT_PARTIEL),
            "nb_non_payes": sum(1 for _, s in situations if s.statut == STATUT_NON_PAYE),
        }

    def historique(self, eleve_id: int) -> list[Paiement]:
        return self.paiements.lister_par_eleve(eleve_id)

    def situations(self, recherche: str = "", classe: str | None = None,
                   statut: str | None = None) -> list[tuple]:
        """Liste (élève, situation) filtrable par statut de paiement."""
        resultat = []
        for eleve in self.eleves.lister(recherche, classe):
            sit = self.situation(eleve.id)
            if statut is None or sit.statut == statut:
                resultat.append((eleve, sit))
        return resultat

    def enregistrer_paiement(self, eleve_id, montant, date_paiement, mode) -> Paiement:
        utilisateur = None
        if self.auth is not None:
            if not self.auth.peut("paiement.encaisser"):
                raise ErreurMetier(
                    "Votre rôle ne permet pas d'enregistrer un paiement.")
            utilisateur = self.auth.utilisateur

        montant = self._valider_montant(montant)
        date_paiement = self._valider_date(date_paiement)
        if mode not in MODES:
            raise ErreurMetier("Mode de paiement invalide.")

        sit = self.situation(eleve_id)
        if sit.solde == 0:
            raise ErreurMetier("Cet élève a déjà tout payé.")
        if montant > sit.solde:
            raise ErreurMetier(
                f"Le montant saisi ({montant}) dépasse le solde restant ({sit.solde}).")

        p = Paiement(
            None, eleve_id, None, montant, date_paiement, mode, sit.solde - montant,
            utilisateur["id"] if utilisateur else None,
            utilisateur["nom_complet"] if utilisateur else None,
        )
        paiement_id = self.paiements.ajouter(p)
        return self.paiements.obtenir(paiement_id)  # avec son numéro de reçu

    def peut_annuler(self) -> bool:
        return self.auth is None or self.auth.peut("paiement.annuler")

    def annuler_paiement(self, paiement_id: int, motif: str) -> Paiement:
        """Annule un paiement (jamais supprimé) ; motif obligatoire."""
        if not self.peut_annuler():
            raise ErreurMetier("Seul un administrateur peut annuler un paiement.")
        motif = str(motif).strip()
        if len(motif) < 5:
            raise ErreurMetier(
                "Le motif de l'annulation est obligatoire (5 caractères minimum).")
        paiement = self.paiements.obtenir(paiement_id)
        if paiement is None:
            raise ErreurMetier("Paiement introuvable.")
        if paiement.annule:
            raise ErreurMetier("Ce paiement est déjà annulé.")
        par = None
        if self.auth is not None and self.auth.utilisateur is not None:
            par = self.auth.utilisateur["nom_complet"]
        quand = datetime.now().isoformat(timespec="seconds")
        self.paiements.annuler(paiement_id, motif, par, quand)
        return self.paiements.obtenir(paiement_id)

    def recu(self, paiement_id: int):
        """Retrouve un reçu déjà émis : retourne (élève, paiement)."""
        paiement = self.paiements.obtenir(paiement_id)
        if paiement is None:
            raise ErreurMetier("Reçu introuvable.")
        return self.eleves.get(paiement.eleve_id), paiement

    def derniers_paiements(self, limite: int = 6) -> list[tuple]:
        """Derniers paiements valides : liste de (élève, paiement)."""
        return [(self.eleves.get(p.eleve_id), p)
                for p in self.paiements.derniers(limite)]

    @staticmethod
    def _valider_montant(valeur) -> int:
        try:
            montant = int("".join(str(valeur).split()))
        except ValueError:
            raise ErreurMetier("Le montant doit être un nombre entier.") from None
        if montant <= 0:
            raise ErreurMetier("Le montant doit être supérieur à 0.")
        return montant

    @staticmethod
    def _valider_date(valeur) -> str:
        try:
            d = datetime.strptime(str(valeur).strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ErreurMetier("Date invalide (format attendu : AAAA-MM-JJ).") from None
        if d > date.today():
            raise ErreurMetier("La date du paiement ne peut pas être dans le futur.")
        return d.isoformat()