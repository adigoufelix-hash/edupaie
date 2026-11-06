import hashlib
import sqlite3
from datetime import date, datetime, timedelta

from edupaie.services import releve_import
from edupaie.services.paiement_service import ErreurMetier

TOLERANCE_JOURS = 2  # écart accepté entre la date du relevé et celle du paiement
PORTEE_CHOIX = 10    # fenêtre de la recherche manuelle d'un paiement
OPERATEURS = ("Flooz", "T-Money", "Autre")
ETATS = {
    "rapproche": "Rapproché", "alerte": "Paiement annulé !",
    "propose_sur": "Correspondance sûre", "propose_probable": "Correspondance probable",
    "sans_paiement": "Sans paiement enregistré", "ignore": "Ignoré",
}


def _fcfa(valeur) -> str:
    return f"{int(valeur):,}".replace(",", " ") + " FCFA"


def _eleve(ligne) -> str:
    return f"{ligne['nom']} {ligne['prenom']}"


class RapprochementService:
    def __init__(self, repo, auth=None, maintenant=datetime.now):
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self.maintenant = maintenant

    def _exiger(self):
        if self.auth is not None and not self.auth.peut("rapprochement.gerer"):
            raise ErreurMetier("Le rapprochement mobile money est réservé à l'administrateur.")

    def _qui(self) -> str:
        utilisateur = getattr(self.auth, "utilisateur", None) or {}
        return utilisateur.get("nom_complet", "")

    def _quand(self) -> str:
        return self.maintenant().isoformat(timespec="seconds")

    @staticmethod
    def _dates(debut, fin):
        try:
            d, f = date.fromisoformat(str(debut)), date.fromisoformat(str(fin))
        except ValueError:
            raise ErreurMetier("Dates invalides.") from None
        if d > f:
            raise ErreurMetier("La date de début doit précéder la date de fin.")
        return d, f

    def periode_par_defaut(self):
        """Toute la durée des relevés importés, sinon le mois en cours."""
        self._exiger()
        bornes = self.repo.bornes()
        if bornes:
            return bornes
        aujourdhui = self.maintenant().date()
        return aujourdhui.replace(day=1).isoformat(), aujourdhui.isoformat()

    # --- Import --------------------------------------------------------------------------
    def importer(self, valides, operateur):
        """Enregistre les opérations lues (releve_import.normaliser). Les doublons sont ignorés."""
        self._exiger()
        if not valides:
            raise ErreurMetier("Aucune opération valide à importer.")
        operateur = " ".join(str(operateur or "").split())[:30] or "Autre"
        vus, lignes = {}, []
        for l in valides:
            if l.get("reference"):
                brut = f"ref|{operateur}|{l['reference']}"
            else:  # sans n° de transaction : deux opérations identiques restent distinctes
                cle = (l["date"], l["montant"], releve_import.cle(l.get("libelle")))
                vus[cle] = vus.get(cle, 0) + 1
                brut = f"sans|{operateur}|{cle[0]}|{cle[1]}|{cle[2]}|{vus[cle]}"
            lignes.append((hashlib.sha256(brut.encode("utf-8")).hexdigest(), l))
        importees, doublons = self.repo.ajouter_lignes(
            lignes, operateur, self._qui(), self._quand())
        return {"operateur": operateur, "importees": importees, "doublons": doublons,
                "debut": min(l["date"] for l in valides), "fin": max(l["date"] for l in valides)}

    # --- Analyse ---------------------------------------------------------------------------
    @staticmethod
    def _ecart(ligne, paiement) -> int:
        return abs((date.fromisoformat(ligne["date_operation"])
                    - date.fromisoformat(paiement["date_paiement"])).days)

    def _proposer(self, lignes, libres):
        """{id de la ligne : (paiement, 'sure' ou 'probable', nombre de candidats)}."""
        pris, resultat = set(), {}

        def candidats(ligne):
            return [p for p in libres if p["id"] not in pris and p["montant"] == ligne["montant"]
                    and self._ecart(ligne, p) <= TOLERANCE_JOURS]

        for passe in (1, 2):
            for ligne in lignes:
                if ligne["id"] in resultat:
                    continue
                c = candidats(ligne)
                if passe == 1 and len(c) == 1:  # un seul paiement possible : correspondance sûre
                    resultat[ligne["id"]] = (c[0], "sure", 1)
                    pris.add(c[0]["id"])
                elif passe == 2 and c:  # plusieurs possibles : on propose le plus proche
                    meilleur = min(c, key=lambda p: (self._ecart(ligne, p), p["id"]))
                    resultat[ligne["id"]] = (meilleur, "probable", len(c))
                    pris.add(meilleur["id"])
        return resultat

    def analyser(self, debut, fin) -> dict:
        self._exiger()
        d, f = self._dates(debut, fin)
        lignes = [dict(r) for r in self.repo.lignes(d.isoformat(), f.isoformat())]
        marge = timedelta(days=TOLERANCE_JOURS)
        paiements = [dict(r) for r in self.repo.paiements_mm(
            (d - marge).isoformat(), (f + marge).isoformat())]
        libres = [p for p in paiements if not p["lie"]]
        propositions = self._proposer([l for l in lignes if l["statut"] == "a_traiter"], libres)
        proposes = {p["id"] for p, _, _ in propositions.values()}

        sorties = []
        for l in lignes:
            sortie = {"id": l["id"], "date": l["date_operation"], "montant": l["montant"],
                      "reference": l["reference"] or "", "libelle": l["libelle"] or "",
                      "statut": l["statut"], "motif": l["motif"] or "",
                      "proposition": None, "paiement": None}
            if l["statut"] == "rapproche" and l["paiement_id"]:
                sortie["paiement"] = {
                    "id": l["paiement_id"], "numero_recu": l["numero_recu"],
                    "eleve": _eleve(l), "classe": l["classe"],
                    "date_paiement": l["date_paiement"], "caissier": l["encaisse_par"] or "",
                    "annule": bool(l["paiement_annule"])}
                sortie["etat"] = "alerte" if l["paiement_annule"] else "rapproche"
            elif l["statut"] == "ignore":
                sortie["etat"] = "ignore"
            elif l["id"] in propositions:
                p, certitude, nombre = propositions[l["id"]]
                sortie["proposition"] = {
                    "paiement_id": p["id"], "certitude": certitude, "alternatives": nombre - 1,
                    "numero_recu": p["numero_recu"], "eleve": _eleve(p), "classe": p["classe"],
                    "date_paiement": p["date_paiement"], "caissier": p["encaisse_par"] or ""}
                sortie["etat"] = "propose_sur" if certitude == "sure" else "propose_probable"
            else:
                sortie["etat"] = "sans_paiement"
            sorties.append(sortie)

        sans_trace = [{"id": p["id"], "numero_recu": p["numero_recu"], "eleve": _eleve(p),
                       "classe": p["classe"], "date_paiement": p["date_paiement"],
                       "montant": p["montant"], "caissier": p["encaisse_par"] or ""}
                      for p in libres
                      if p["id"] not in proposes
                      and d.isoformat() <= p["date_paiement"] <= f.isoformat()]
        dans_periode = [p for p in paiements
                        if d.isoformat() <= p["date_paiement"] <= f.isoformat()]

        def total(etats):
            choisies = [s for s in sorties if s["etat"] in etats]
            return len(choisies), sum(s["montant"] for s in choisies)

        valables = [s for s in sorties if s["etat"] != "ignore"]
        nb_rapproche, montant_rapproche = total(("rapproche", "alerte"))
        nb_propose, _ = total(("propose_sur", "propose_probable"))
        nb_sans, montant_sans = total(("sans_paiement",))
        nb_ignore, montant_ignore = total(("ignore",))
        resume = {
            "nb_lignes": len(valables), "montant_releve": sum(s["montant"] for s in valables),
            "nb_rapproche": nb_rapproche, "montant_rapproche": montant_rapproche,
            "nb_propose": nb_propose, "nb_sans_paiement": nb_sans,
            "montant_sans_paiement": montant_sans, "nb_ignore": nb_ignore,
            "montant_ignore": montant_ignore,
            "nb_sans_trace": len(sans_trace),
            "montant_sans_trace": sum(p["montant"] for p in sans_trace),
            "nb_enregistre": len(dans_periode),
            "montant_enregistre": sum(p["montant"] for p in dans_periode),
            "nb_alertes": sum(1 for s in sorties if s["etat"] == "alerte")}
        resume["ecart"] = resume["montant_releve"] - resume["montant_rapproche"]
        return {"debut": d.isoformat(), "fin": f.isoformat(), "lignes": sorties,
                "sans_trace": sans_trace, "resume": resume}

    def candidats(self, ligne_id) -> list[dict]:
        """Paiements libres du même montant, autour de la date de l'opération."""
        self._exiger()
        ligne = self.repo.ligne(ligne_id)
        if ligne is None or ligne["statut"] != "a_traiter":
            raise ErreurMetier("Cette opération du relevé est déjà traitée ou n'existe plus.")
        jour, marge = date.fromisoformat(ligne["date_operation"]), timedelta(days=PORTEE_CHOIX)
        choisis = [dict(p) for p in self.repo.paiements_mm(
            (jour - marge).isoformat(), (jour + marge).isoformat())
            if not p["lie"] and p["montant"] == ligne["montant"]]
        choisis.sort(key=lambda p: (self._ecart(ligne, p), p["id"]))
        return [{"id": p["id"], "numero_recu": p["numero_recu"], "date_paiement": p["date_paiement"],
                 "montant": p["montant"], "eleve": _eleve(p), "classe": p["classe"],
                 "caissier": p["encaisse_par"] or ""} for p in choisis]

    # --- Actions --------------------------------------------------------------------------------
    def rapprocher(self, ligne_id, paiement_id) -> dict:
        self._exiger()
        ligne = self.repo.ligne(ligne_id)
        if ligne is None or ligne["statut"] != "a_traiter":
            raise ErreurMetier("Cette opération du relevé est déjà traitée ou n'existe plus.")
        paiement = self.repo.paiement(paiement_id)
        if paiement is None or paiement["mode"] != "mobile_money":
            raise ErreurMetier("Ce paiement n'existe pas ou n'a pas été fait par mobile money.")
        if paiement["annule"]:
            raise ErreurMetier("Ce paiement est annulé.")
        if paiement["lie"]:
            raise ErreurMetier("Ce paiement est déjà rapproché d'une autre opération du relevé.")
        if paiement["montant"] != ligne["montant"]:
            raise ErreurMetier(f"Les montants diffèrent : relevé {_fcfa(ligne['montant'])}, "
                               f"paiement {_fcfa(paiement['montant'])}.")
        try:
            self.repo.lier_plusieurs([(ligne_id, paiement_id)], self._qui(), self._quand())
        except (LookupError, sqlite3.IntegrityError):
            raise ErreurMetier("Rapprochement impossible : l'opération ou le paiement vient "
                               "d'être modifié.") from None
        return {"date": ligne["date_operation"], "montant": ligne["montant"],
                "numero_recu": paiement["numero_recu"]}

    def rapprocher_automatiquement(self, debut, fin) -> dict:
        """Rapproche uniquement les correspondances sûres ; les probables restent à valider."""
        analyse = self.analyser(debut, fin)
        liens = [(l["id"], l["proposition"]["paiement_id"]) for l in analyse["lignes"]
                 if l["proposition"] and l["proposition"]["certitude"] == "sure"]
        if liens:
            try:
                self.repo.lier_plusieurs(liens, self._qui(), self._quand())
            except (LookupError, sqlite3.IntegrityError):
                raise ErreurMetier("Rapprochement impossible : des données viennent d'être "
                                   "modifiées. Réessaie.") from None
        return {"rapproches": len(liens)}

    def ignorer(self, ligne_id, motif) -> dict:
        self._exiger()
        motif = " ".join(str(motif or "").split())[:120]
        if len(motif) < 5:
            raise ErreurMetier("Indique le motif (5 caractères minimum).")
        ligne = self.repo.ligne(ligne_id)
        if ligne is None or ligne["statut"] != "a_traiter":
            raise ErreurMetier("Cette opération du relevé est déjà traitée ou n'existe plus.")
        self.repo.ignorer(ligne_id, motif, self._qui(), self._quand())
        return {"date": ligne["date_operation"], "montant": ligne["montant"], "motif": motif}

    def defaire(self, ligne_id) -> dict:
        """Remet l'opération à traiter (annule un rapprochement ou une mise à l'écart)."""
        self._exiger()
        ligne = self.repo.ligne(ligne_id)
        if ligne is None or ligne["statut"] == "a_traiter":
            raise ErreurMetier("Cette opération n'a ni rapprochement ni mise à l'écart à annuler.")
        self.repo.defaire(ligne_id, self._qui(), self._quand())
        return {"date": ligne["date_operation"], "montant": ligne["montant"]}