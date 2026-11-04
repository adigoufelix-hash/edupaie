from datetime import datetime
from urllib.parse import quote

from edupaie.services.echeancier_service import normaliser_telephone
from edupaie.services.ecole import courant
from edupaie.services.paiement_service import MODES, ErreurMetier

LIBELLES_MODES = {"especes": "Espèces", "cheque": "Chèque", "virement": "Virement",
                  "mobile_money": "Mobile money"}
MAX_LIGNES = 5            # lignes de détail par rubrique
MAX_CAISSIERS = 8
LONGUEUR_MAX_LIEN = 1900  # au-delà, certains navigateurs refusent d'ouvrir le lien


def _fcfa(valeur) -> str:
    return f"{int(valeur):,}".replace(",", " ") + " FCFA"


def _date_fr(iso: str) -> str:
    annee, mois, jour = str(iso)[:10].split("-")
    return f"{jour}/{mois}/{annee}"


def _periode(debut, fin) -> str:
    return _date_fr(debut) if debut == fin else f"du {_date_fr(debut)} au {_date_fr(fin)}"


def _propre(texte, maximum=60) -> str:
    """Une seule ligne, sans retours à la ligne, longueur limitée."""
    return " ".join(str(texte or "").split())[:maximum]


def _pluriel(nombre, mot) -> str:
    return f"{nombre} {mot}" + ("s" if nombre > 1 else "")


def _champ(ligne, nom):
    try:
        return ligne[nom]
    except (KeyError, IndexError):
        return None


def _limiter(lignes, maximum):
    if maximum <= 0:
        return ["- Détail dans EduPaie."] if lignes else []
    if len(lignes) <= maximum:
        return lignes
    return lignes[:maximum] + [f"- ... et {len(lignes) - maximum} autre(s)"]


class ResumeJourService:
    def __init__(self, caisse, repo, auth=None, ecole=courant, maintenant=datetime.now):
        self.caisse = caisse
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self.ecole = ecole
        self.maintenant = maintenant

    # --- Numéro de la direction ---------------------------------------------------------
    def peut_definir_numero(self) -> bool:
        return self.auth is None or self.auth.peut("ecole.gerer")

    def numero(self) -> str:
        return self.repo.numero()

    def numero_affiche(self) -> str:
        numero = self.numero()
        if not numero:
            return ""
        if numero.startswith("228") and len(numero) == 11:
            return f"+228 {numero[3:5]} {numero[5:7]} {numero[7:9]} {numero[9:11]}"
        return "+" + numero

    def definir_numero(self, texte):
        """Enregistre le numéro WhatsApp de la direction ; vide = le retirer."""
        if not self.peut_definir_numero():
            raise ErreurMetier("Seul un administrateur peut enregistrer le numéro de la direction.")
        brut = str(texte or "").strip()
        if not brut:
            self.repo.definir_numero("")
            return None
        numero = normaliser_telephone(brut)
        if numero is None:
            raise ErreurMetier("Numéro invalide : saisis 8 chiffres (Togo) ou un numéro "
                               "international, par exemple +228 90 12 34 56.")
        self.repo.definir_numero(numero)
        return numero

    # --- Le message ----------------------------------------------------------------------
    def _voit_tout(self) -> bool:
        return self.auth is None or self.auth.peut("caisse.toutes")

    def message(self, debut, fin, max_lignes=MAX_LIGNES) -> str:
        c = self.caisse.cloture(debut, fin)  # vérifie aussi le droit de consulter la caisse
        ecole = self.ecole()
        lignes = [f"*{_propre(ecole.nom_affiche, 80)}*",
                  f"Résumé de caisse - {_periode(c['debut'], c['fin'])}", c["portee"], ""]

        if c["nb"]:
            lignes.append(f"*Total encaissé : {_fcfa(c['total'])}* "
                          f"({_pluriel(c['nb'], 'paiement')})")
            lignes += ["", "*Par mode*"]
            lignes += [f"- {LIBELLES_MODES[m]} : {_fcfa(c['par_mode'][m])}"
                       for m in MODES if c["par_mode"].get(m)]
            lignes += ["", "*Par caissier*"]
            caissiers = [f"- {_propre(k['nom'], 40)} : {_pluriel(k['nb'], 'paiement')}, "
                         f"{_fcfa(k['total'])}" for k in c["caissiers"]]
            lignes += (caissiers[:MAX_CAISSIERS] + (
                [f"- ... et {len(caissiers) - MAX_CAISSIERS} autre(s)"]
                if len(caissiers) > MAX_CAISSIERS else []))
        else:
            lignes.append("Aucun paiement enregistré sur cette période.")

        annules = c["annules"]
        if annules["nb"]:
            lignes += ["", f"*Paiements annulés : {annules['nb']}* "
                           f"({_fcfa(annules['total'])} non comptés)"]
            detail = []
            for p in annules["paiements"]:
                ligne = f"- {p['numero_recu']} : {_fcfa(p['montant'])}"
                motif = _propre(_champ(p, "motif_annulation"))
                detail.append(ligne + (f" - motif : {motif}" if motif else ""))
            lignes += _limiter(detail, max_lignes)

        if self._voit_tout():
            remises = self.repo.remises_periode(c["debut"], c["fin"])
            if remises:
                total = sum(r["montant"] for r in remises)
                lignes += ["", f"*Remises accordées : {len(remises)}* ({_fcfa(total)})"]
                detail = [f"- {_propre(r['nom'], 30)} {_propre(r['prenom'], 30)} "
                          f"({_propre(r['classe'], 20)}) : {_fcfa(r['montant'])} - "
                          f"{_propre(r['motif'], 40)}" for r in remises]
                lignes += _limiter(detail, max_lignes)

        maintenant = self.maintenant()
        par = c.get("genere_par") or "EduPaie"
        lignes += ["", f"Envoyé par {par} le {maintenant:%d/%m/%Y} à {maintenant:%H:%M} "
                       "via EduPaie."]
        return "\n".join(lignes)

    def lien_whatsapp(self, debut, fin) -> str:
        """Lien qui ouvre WhatsApp avec le message prêt (le numéro de la direction si connu)."""
        numero = self.numero()
        base = f"https://wa.me/{numero}" if numero else "https://wa.me/"
        for maximum in (MAX_LIGNES, 3, 1, 0):  # on raccourcit si le lien est trop long
            lien = f"{base}?text={quote(self.message(debut, fin, maximum), safe='')}"
            if len(lien) <= LONGUEUR_MAX_LIEN:
                break
        return lien