from datetime import date

from edupaie.services.paiement_service import ErreurMetier

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def libelle_mois(mois: str) -> str:
    """'2026-10' -> 'octobre 2026'."""
    annee, numero = mois.split("-")
    return f"{MOIS[int(numero) - 1]} {annee}"


def _taux(numerateur, denominateur):
    return None if denominateur <= 0 else numerateur * 100 / denominateur


def _classe_vide(nom: str, suivi: bool) -> dict:
    return {"classe": nom, "suivi": suivi, "eleves": 0, "total_du": 0, "remises": 0, "net": 0,
            "paye": 0, "reste": 0, "exigible": 0, "couvert": 0, "retard": 0,
            "en_retard": 0, "soldes": 0, "partiels": 0, "non_payes": 0}


class RecouvrementService:
    def __init__(self, repo, auth=None, aujourdhui=date.today):
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self.aujourdhui = aujourdhui

    def _exiger(self):
        if self.auth is not None and not self.auth.peut("recouvrement.voir"):
            raise ErreurMetier("Le tableau de recouvrement est réservé à l'administrateur.")

    def annees(self) -> list[str]:
        self._exiger()
        return self.repo.annees()

    def tableau(self, annee: str, date_ref=None) -> dict:
        """Situation d'une année scolaire à la date donnée (aujourd'hui par défaut)."""
        self._exiger()
        ref = str(date_ref or self.aujourdhui().isoformat())
        try:
            date.fromisoformat(ref)
        except ValueError:
            raise ErreurMetier("Date de situation invalide.") from None

        tranches = {}
        for e in self.repo.echeances(annee):
            tranches.setdefault(e["classe"], []).append((e["date_limite"], e["pourcentage"]))
        for liste in tranches.values():
            liste.sort()

        classes, prevu_par_mois = {}, {}
        for e in self.repo.eleves(annee):
            c = classes.setdefault(e["classe"], _classe_vide(e["classe"], e["classe"] in tranches))
            net = max(e["total_du"] - e["remises"], 0)
            paye = e["paye"]
            reste = max(net - paye, 0)
            c["eleves"] += 1
            c["total_du"] += e["total_du"]
            c["remises"] += e["remises"]
            c["net"] += net
            c["paye"] += paye
            c["reste"] += reste
            if reste == 0:
                c["soldes"] += 1
            elif paye == 0:
                c["non_payes"] += 1
            else:
                c["partiels"] += 1
            liste = tranches.get(e["classe"])
            if not liste:
                continue
            # Même calcul que l'écran Impayés : part cumulée des tranches échues
            cumul = precedent = exigible = 0
            for date_limite, pourcentage in liste:
                cumul += pourcentage
                cumule = net * min(cumul, 100) // 100
                mois = date_limite[:7]
                prevu_par_mois[mois] = prevu_par_mois.get(mois, 0) + (cumule - precedent)
                precedent = cumule
                if date_limite <= ref:
                    exigible = cumule
            retard = max(exigible - paye, 0)
            c["exigible"] += exigible
            c["couvert"] += min(paye, exigible)
            c["retard"] += retard
            if retard:
                c["en_retard"] += 1

        ordre = {nom: i for i, nom in enumerate(self.repo.classes_ordonnees())}
        liste_classes = sorted(classes.values(),
                               key=lambda c: (ordre.get(c["classe"], len(ordre)), c["classe"]))
        total = _classe_vide("TOTAL", any(c["suivi"] for c in liste_classes))
        for c in liste_classes:
            for cle in total:
                if cle not in ("classe", "suivi"):
                    total[cle] += c[cle]
        for c in liste_classes + [total]:
            c["taux"] = _taux(c["paye"], c["net"])
            c["taux_exigible"] = _taux(c["couvert"], c["exigible"])

        encaisse_par_mois = {r["mois"]: r["montant"] for r in self.repo.paiements_par_mois(annee)}
        mois_ref = ref[:7]
        lignes, cumul_e, cumul_p = [], 0, 0
        for mois in sorted(set(encaisse_par_mois) | set(prevu_par_mois)):
            encaisse, prevu = encaisse_par_mois.get(mois, 0), prevu_par_mois.get(mois, 0)
            a_venir = mois > mois_ref
            cumul_e += encaisse
            cumul_p += prevu
            lignes.append({
                "mois": mois, "libelle": libelle_mois(mois), "encaisse": encaisse,
                "prevu": prevu, "a_venir": a_venir, "en_cours": mois == mois_ref,
                "taux": None if a_venir else _taux(encaisse, prevu),
                "cumul_encaisse": cumul_e, "cumul_prevu": cumul_p,
                "taux_cumule": None if a_venir else _taux(cumul_e, cumul_p)})

        return {"annee": annee, "date_ref": ref, "classes": liste_classes, "total": total,
                "mois": lignes,
                "classes_sans_echeancier": [c["classe"] for c in liste_classes
                                            if not c["suivi"]]}