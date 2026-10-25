from datetime import datetime

from edupaie.services.paiement_service import MODES, ErreurMetier


class CaisseService:
    def __init__(self, paiement_repo, auth=None):
        self.paiements = paiement_repo
        self.auth = auth  # None dans les tests : tous les caissiers, sans contrôle

    def _portee(self):
        """Retourne (utilisateur_id à filtrer ou None, libellé de la portée)."""
        if self.auth is None:
            return None, "Tous les caissiers"
        if not self.auth.peut("caisse.voir"):
            raise ErreurMetier("Votre rôle ne permet pas de consulter la caisse.")
        if self.auth.peut("caisse.toutes"):
            return None, "Tous les caissiers"
        utilisateur = self.auth.utilisateur
        return utilisateur["id"], f"Caissier : {utilisateur['nom_complet']}"

    @staticmethod
    def _valider_date(valeur) -> str:
        try:
            return datetime.strptime(str(valeur).strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ErreurMetier("Date invalide (format attendu : AAAA-MM-JJ).") from None

    def cloture(self, debut, fin) -> dict:
        """Totaux de la période, par caissier et par mode de paiement."""
        utilisateur_id, portee = self._portee()
        debut, fin = self._valider_date(debut), self._valider_date(fin)
        if debut > fin:
            raise ErreurMetier("La date de début doit précéder la date de fin.")

        par_caissier = {}
        par_mode = dict.fromkeys(MODES, 0)
        annules = {"nb": 0, "total": 0, "paiements": []}
        total = nb = 0
        for ligne in self.paiements.lister_periode(debut, fin, utilisateur_id):
            if ligne["annule"]:
                annules["nb"] += 1
                annules["total"] += ligne["montant"]
                annules["paiements"].append(ligne)
                continue
            nom = ligne["encaisse_par"] or "Non renseigné"
            c = par_caissier.setdefault(nom, {
                "nom": nom, "nb": 0, "total": 0,
                "par_mode": dict.fromkeys(MODES, 0), "paiements": []})
            c["nb"] += 1
            c["total"] += ligne["montant"]
            c["par_mode"][ligne["mode"]] += ligne["montant"]
            c["paiements"].append(ligne)
            par_mode[ligne["mode"]] += ligne["montant"]
            total += ligne["montant"]
            nb += 1

        utilisateur = self.auth.utilisateur if self.auth is not None else None
        return {
            "debut": debut, "fin": fin, "portee": portee,
            "genere_par": utilisateur["nom_complet"] if utilisateur else None,
            "caissiers": sorted(par_caissier.values(), key=lambda c: c["nom"].lower()),
            "par_mode": par_mode, "total": total, "nb": nb, "annules": annules,
        }