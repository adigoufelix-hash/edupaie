from collections import OrderedDict
from datetime import date, datetime
from urllib.parse import quote

from edupaie.services.echeancier_service import normaliser_telephone
from edupaie.services.paiement_service import ErreurMetier

DELAI_MIN_JOURS = 7        # un parent relancé depuis moins de 7 jours n'est pas recoché
MAX_ENFANTS_MESSAGE = 6    # nombre d'enfants détaillés dans un message groupé
LONGUEUR_MAX_LIEN = 1900   # au-delà, certains navigateurs refusent d'ouvrir le lien


def _fcfa(valeur) -> str:
    return f"{int(valeur):,}".replace(",", " ") + " FCFA"


def _date_fr(iso) -> str:
    annee, mois, jour = str(iso)[:10].split("-")
    return f"{jour}/{mois}/{annee}"


class RelanceService:
    def __init__(self, echeancier, repo, auth=None, maintenant=datetime.now):
        self.echeancier = echeancier  # EcheancierService : calcule les impayés
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self.maintenant = maintenant

    def _exiger(self):
        if self.auth is not None and not self.auth.peut("impayes.relancer"):
            raise ErreurMetier("Votre rôle ne permet pas d'envoyer des relances.")

    def classes(self) -> list[str]:
        return self.echeancier.classes()

    # --- Le message ------------------------------------------------------------------------
    def message(self, enfants, max_enfants=MAX_ENFANTS_MESSAGE) -> str:
        """Un enfant : le message habituel. Plusieurs : un seul message qui les liste."""
        if len(enfants) == 1:
            return self.echeancier.message_relance(enfants[0])
        lignes = [f"Bonjour, nous vous informons que {len(enfants)} de vos enfants ont un "
                  "solde en retard :"]
        for e in enfants[:max_enfants]:
            lignes.append(f"- {e['nom']} ({e['classe']}) : {_fcfa(e['retard'])} "
                          f"(échéance « {e['tranche']} » du {_date_fr(e['date_limite'])})")
        if len(enfants) > max_enfants:
            lignes.append(f"- ... et {len(enfants) - max_enfants} autre(s)")
        total = _fcfa(sum(e["retard"] for e in enfants))
        lignes.append(f"Total en retard : {total}. Merci de passer régulariser à "
                      "l'administration de l'école. Cordialement.")
        return "\n".join(lignes)

    # --- La liste des parents à relancer -------------------------------------------------------
    def preparer(self, date_ref=None, classe=None) -> dict:
        self._exiger()
        impayes = self.echeancier.impayes(date_ref, classe)
        lignes = impayes["lignes"]
        aujourdhui = self.maintenant().date()
        dernieres = self.repo.dernieres([l["eleve_id"] for l in lignes])

        groupes, sans_numero = OrderedDict(), []
        for l in lignes:
            numero = normaliser_telephone(l.get("telephone") or "")
            if numero is None:
                sans_numero.append({"eleve_id": l["eleve_id"], "nom": l["nom"],
                                    "classe": l["classe"], "retard": l["retard"]})
            else:  # même numéro = même parent : un seul message pour ses enfants
                groupes.setdefault(numero, []).append(l)

        destinataires = []
        for numero, enfants in groupes.items():
            dates = [dernieres[e["eleve_id"]] for e in enfants if e["eleve_id"] in dernieres]
            derniere = max(dates) if dates else None
            jours = (aujourdhui - date.fromisoformat(derniere[:10])).days if derniere else None
            tuteurs = sorted({e["tuteur"] for e in enfants if e.get("tuteur")})
            destinataires.append({
                "cle": numero, "telephone": numero, "tuteur": " / ".join(tuteurs),
                "enfants": enfants, "nb_eleves": len(enfants),
                "retard": sum(e["retard"] for e in enfants), "message": self.message(enfants),
                "derniere": derniere, "jours_depuis": jours,
                "recente": jours is not None and jours < DELAI_MIN_JOURS})
        return {"date_ref": impayes["date_ref"], "destinataires": destinataires,
                "sans_numero": sans_numero, "nb_eleves": len(lignes),
                "total_retard": impayes["total_retard"],
                "sans_echeancier": impayes["sans_echeancier"]}

    # --- Ouvrir WhatsApp et noter la relance ------------------------------------------------------
    def lien_et_noter(self, date_ref, classe, cle) -> dict:
        """Retourne le lien WhatsApp d'un parent et enregistre la relance de ses enfants."""
        self._exiger()
        preparation = self.preparer(date_ref, classe)
        dest = next((d for d in preparation["destinataires"] if d["cle"] == cle), None)
        if dest is None:
            raise ErreurMetier("Ce parent n'est plus en retard à cette date, ou n'a pas de "
                               "numéro valide : actualise l'écran.")
        base = f"https://wa.me/{dest['telephone']}?text="
        for maximum in (MAX_ENFANTS_MESSAGE, 3, 1, 0):  # on raccourcit si le lien est trop long
            lien = base + quote(self.message(dest["enfants"], maximum), safe="")
            if len(lien) <= LONGUEUR_MAX_LIEN:
                break
        quand = self.maintenant().isoformat(timespec="seconds")
        utilisateur = getattr(self.auth, "utilisateur", None) or {}
        par = utilisateur.get("nom_complet", "")
        for e in dest["enfants"]:
            self.repo.ajouter(e["eleve_id"], quand, e["retard"], e["tranche"], par)
        return {"lien": lien, "nb_eleves": dest["nb_eleves"], "retard": dest["retard"]}