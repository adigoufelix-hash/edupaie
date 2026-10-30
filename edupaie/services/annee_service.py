import re
from datetime import datetime

from edupaie.services.paiement_service import ErreurMetier

_ANNEE = re.compile(r"(\d{4})\s*[-/–]\s*(\d{4})")
_FORME_CLASSE = re.compile(r"^(?P<niveau>.*?)(?:\s+(?P<section>[A-Za-z0-9]{1,2}))?$")


def valider_annee(texte) -> str:
    m = _ANNEE.fullmatch(str(texte or "").strip())
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise ErreurMetier("Année scolaire invalide (exemple : 2026-2027).")
    return f"{m.group(1)}-{m.group(2)}"


def annee_suivante(annee) -> str:
    debut = int(valider_annee(annee)[:4]) + 1
    return f"{debut}-{debut + 1}"


def _decouper(nom: str) -> tuple[str, str]:
    """« 6e A » -> (« 6e », « A ») ; « 2nde » -> (« 2nde », « »)."""
    m = _FORME_CLASSE.match(str(nom).strip())
    return (m.group("niveau").strip() or str(nom).strip(), m.group("section") or "")


def proposer_destination(classes, classe):
    """Classe supérieure probable d'après l'ordre des classes ; None = dernière classe."""
    niveaux = []
    for c in classes:
        niveau = _decouper(c)[0]
        if niveau.casefold() not in [n.casefold() for n in niveaux]:
            niveaux.append(niveau)
    niveau, section = _decouper(classe)
    cles = [n.casefold() for n in niveaux]
    if niveau.casefold() not in cles or cles.index(niveau.casefold()) + 1 >= len(niveaux):
        return None
    suivant = niveaux[cles.index(niveau.casefold()) + 1]
    candidates = [c for c in classes if _decouper(c)[0].casefold() == suivant.casefold()]
    meme_section = [c for c in candidates if _decouper(c)[1].casefold() == section.casefold()]
    return (meme_section or candidates)[0]


class AnneeService:
    def __init__(self, repo, classes_repo, auth=None, sauvegarde=None):
        self.repo = repo
        self.classes_repo = classes_repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self.sauvegarde = sauvegarde  # copie de sécurité faite avant le passage

    def _exiger(self):
        if self.auth is not None and not self.auth.peut("annee.gerer"):
            raise ErreurMetier("Seul un administrateur peut gérer les années scolaires.")

    # --- Année active -----------------------------------------------------------------
    def active(self):
        """Année affichée par défaut (None : aucune, tout est affiché)."""
        return self.repo.get_parametre("annee_active") or None

    def definir_active(self, annee) -> None:
        self._exiger()
        self.repo.set_parametre("annee_active", valider_annee(annee))

    def annees(self) -> list[str]:
        return self.repo.annees()

    def classes(self) -> list[str]:
        return self.classes_repo.noms()

    def source_proposee(self):
        """Année de départ du prochain passage : l'année active, sinon la plus récente."""
        annees = self.repo.annees()
        return self.active() or (annees[-1] if annees else None)

    def frais_definis(self, classe, annee) -> bool:
        return self.repo.total_frais(classe, annee) > 0

    # --- Préparation du passage -----------------------------------------------------------
    def proposer(self, annee_source) -> dict:
        self._exiger()
        source = valider_annee(annee_source)
        cible = annee_suivante(source)
        classes = self.classes()
        ordre = {c.casefold(): i for i, c in enumerate(classes)}
        passes = self.repo.deja_passes(cible)
        inscrits = self.repo.inscrits(cible)
        eleves = sorted(self.repo.eleves_avec_solde(source), key=lambda e: (
            ordre.get(e["classe"].casefold(), len(ordre)), e["nom"].casefold(),
            e["prenom"].casefold()))
        lignes = []
        for e in eleves:
            if e["id"] in passes:
                statut = "fait"
            elif (e["nom"].casefold(), e["prenom"].casefold()) in inscrits:
                statut = "inscrit"
            else:
                statut = "a_faire"
            lignes.append({
                "eleve_id": e["id"], "nom": e["nom"], "prenom": e["prenom"],
                "classe": e["classe"],
                "arrieres": max(e["total_du"] - e["remises"] - e["paye"], 0),
                "statut": statut,
                "destination": (proposer_destination(classes, e["classe"])
                                if statut == "a_faire" else None)})
        return {"source": source, "cible": cible, "lignes": lignes}

    def reprendre_frais(self, annee_source) -> dict:
        """Reprend les frais et l'échéancier de l'année précédente pour la suivante."""
        self._exiger()
        source = valider_annee(annee_source)
        cible = annee_suivante(source)
        resultat = self.repo.copier_frais_et_echeances(source, cible)
        resultat["cible"] = cible
        return resultat

    # --- Exécution -----------------------------------------------------------------------------
    def executer(self, annee_source, plan, reporter_arrieres=True) -> dict:
        """plan : [{eleve_id, destination, reinscrire}] ; une seule transaction."""
        self._exiger()
        source = valider_annee(annee_source)
        cible = annee_suivante(source)
        connues = {c.casefold() for c in self.classes()}
        existants = {e["id"]: e for e in self.repo.eleves_avec_solde(source)}
        passes = self.repo.deja_passes(cible)
        inscrits = self.repo.inscrits(cible)
        lignes, sortants, ignores = [], 0, 0
        for element in plan:
            eleve = existants.get(element.get("eleve_id"))
            if eleve is None:
                raise ErreurMetier(f"Élève introuvable pour l'année {source}.")
            destination = str(element.get("destination") or "").strip()
            if not element.get("reinscrire") or not destination:
                sortants += 1
                continue
            if eleve["id"] in passes or (
                    eleve["nom"].casefold(), eleve["prenom"].casefold()) in inscrits:
                ignores += 1
                continue
            if destination.casefold() not in connues:
                raise ErreurMetier(f"Classe de destination inconnue : « {destination} ».")
            frais = self.repo.total_frais(destination, cible)
            base = frais or eleve["total_du"]  # sinon : l'ancien total est repris
            arrieres = (max(eleve["total_du"] - eleve["remises"] - eleve["paye"], 0)
                        if reporter_arrieres else 0)
            lignes.append({
                "eleve_id": eleve["id"], "nom": eleve["nom"], "prenom": eleve["prenom"],
                "classe_source": eleve["classe"], "classe_cible": destination,
                "base": base, "arrieres": arrieres, "total": base + arrieres,
                "sans_frais": not frais})
        if not lignes:
            raise ErreurMetier("Aucun élève à réinscrire.")
        if self.sauvegarde is not None:
            try:
                self.sauvegarde.sauvegarder("avant-passage")
            except Exception as e:  # sans sauvegarde de sécurité, on ne touche à rien
                raise ErreurMetier("Passage annulé : la sauvegarde de sécurité a "
                                   f"échoué ({e}).") from None
        auteur = (self.auth.utilisateur["nom_complet"]
                  if self.auth is not None and self.auth.utilisateur else None)
        quand = datetime.now().isoformat(timespec="seconds")
        try:
            self.repo.executer_lot(lignes, source, cible, auteur, quand)
        except Exception as e:
            raise ErreurMetier("Passage annulé, aucune donnée n'a été modifiée : "
                               f"{e}") from None
        return {"source": source, "cible": cible, "lignes": lignes,
                "reinscrits": len(lignes), "sortants": sortants, "ignores": ignores,
                "arrieres": sum(l["arrieres"] for l in lignes),
                "sans_frais": sum(1 for l in lignes if l["sans_frais"])}