import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from edupaie.services.licence import (CLE_PUBLIQUE_HEX, ESSAI_JOURS, ErreurLicence,
                                      analyser_licence, construire_cle,
                                      identifiant_machine, lire_cle)
from edupaie.services.paiement_service import ErreurMetier


def _fr(jour: date) -> str:
    return f"{jour:%d/%m/%Y}"


class MarquesMemoire:
    """Marques gardées en mémoire (tests)."""

    def __init__(self):
        self.valeurs = {}

    def lire(self, nom):
        return self.valeurs.get(nom)

    def ecrire(self, nom, valeur):
        self.valeurs[nom] = valeur


class MarquesExternes:
    """Marques gardées hors de la base (registre Windows), pour qu'effacer la base ne
    relance pas la période d'essai."""

    CHEMIN_REGISTRE = r"Software\EduPaie"

    def __init__(self, fichier=None):
        self.fichier = Path(fichier) if fichier else Path.home() / ".edupaie_marques.json"

    def lire(self, nom):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.CHEMIN_REGISTRE) as cle:
                return str(winreg.QueryValueEx(cle, nom)[0])
        except (ImportError, OSError):
            return self._lire_fichier(nom)

    def ecrire(self, nom, valeur):
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.CHEMIN_REGISTRE) as cle:
                winreg.SetValueEx(cle, nom, 0, winreg.REG_SZ, valeur)
        except (ImportError, OSError):
            self._ecrire_fichier(nom, valeur)

    def _lire_fichier(self, nom):
        try:
            return json.loads(self.fichier.read_text(encoding="utf-8")).get(nom)
        except (OSError, ValueError, AttributeError):
            return None

    def _ecrire_fichier(self, nom, valeur):
        try:
            donnees = json.loads(self.fichier.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            donnees = {}
        donnees[nom] = valeur
        try:
            self.fichier.write_text(json.dumps(donnees), encoding="utf-8")
        except OSError:
            pass


@dataclass(frozen=True)
class EtatLicence:
    mode: str                 # "licence", "essai" ou "expire"
    message: str
    machine: str
    reference: date           # date de référence (jamais antérieure à la dernière utilisation)
    jours_restants: int | None = None
    ecole: str | None = None
    licence_id: str | None = None
    expire_le: str | None = None   # AAAA-MM-JJ ; None = sans limite de durée
    probleme: str | None = None    # pourquoi une licence enregistrée est refusée
    avertissement: str | None = None

    @property
    def restreint(self) -> bool:
        return self.mode == "expire"


class LicenceService:
    def __init__(self, repo, cle_publique_hex=CLE_PUBLIQUE_HEX, marques=None, machine=None,
                 aujourdhui=date.today, auth=None):
        self.repo = repo
        self.cle_publique = cle_publique_hex
        self.marques = marques if marques is not None else MarquesExternes()
        self._machine = machine
        self._aujourdhui = aujourdhui
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self._cache = None

    # --- Identité de l'ordinateur --------------------------------------------------------
    def machine(self) -> str:
        if self._machine is None:
            self._machine = identifiant_machine()
        return self._machine

    def configuree(self) -> bool:
        return bool(self.cle_publique)

    # --- Marques d'essai (base + registre) -----------------------------------------------
    def _mac(self, nom: str, jour: str) -> str:
        cle = hashlib.sha256(f"edupaie-marques|{self.machine()}".encode("utf-8")).digest()
        return hmac.new(cle, f"{nom}|{jour}".encode("utf-8"), hashlib.sha256
                        ).hexdigest()[:12]

    def _date_base(self, nom: str):
        brut = self.repo.get(nom)
        try:
            return date.fromisoformat(brut) if brut else None
        except ValueError:
            return None

    def _lire_marque(self, nom: str):
        """(date, altérée) : une marque dont la signature ne correspond pas est altérée."""
        brut = self.marques.lire(nom)
        if not brut:
            return None, False
        jour, _, mac = str(brut).partition(":")
        try:
            valeur = date.fromisoformat(jour)
        except ValueError:
            return None, True
        if not hmac.compare_digest(mac, self._mac(nom, jour)):
            return None, True
        return valeur, False

    def _memoriser(self, nom: str, valeur: date, externe) -> None:
        iso = valeur.isoformat()
        if self.repo.get(nom) != iso:
            self.repo.set(nom, iso)
        marque, altere = externe
        if not altere and marque != valeur:  # une marque altérée n'est jamais « réparée »
            self.marques.ecrire(nom, f"{iso}:{self._mac(nom, iso)}")

    # --- État ------------------------------------------------------------------------------
    def etat(self) -> EtatLicence:
        aujourdhui = self._aujourdhui()
        if self._cache is None or self._cache[0] != aujourdhui:
            self._cache = (aujourdhui, self._calculer(aujourdhui))
        return self._cache[1]

    def restreint(self) -> bool:
        return self.etat().restreint

    def _calculer(self, aujourdhui: date) -> EtatLicence:
        machine = self.machine()
        alteration = False
        dates = {}
        externes = {}
        for nom in ("essai_debut", "derniere_date"):
            externes[nom] = self._lire_marque(nom)
            alteration = alteration or externes[nom][1]
            dates[nom] = [d for d in (self._date_base(nom), externes[nom][0]) if d]
        debut = min(dates["essai_debut"]) if dates["essai_debut"] else aujourdhui
        derniere = max(dates["derniere_date"]) if dates["derniere_date"] else aujourdhui
        reference = max(aujourdhui, derniere)  # on ne revient jamais en arrière
        debut = min(debut, reference)
        horloge_reculee = (derniere - aujourdhui).days > 1
        self._memoriser("essai_debut", debut, externes["essai_debut"])
        if aujourdhui >= derniere and (aujourdhui - derniere).days <= 366:
            derniere = aujourdhui  # un saut de plus d'un an n'est pas mémorisé
        self._memoriser("derniere_date", derniere, externes["derniere_date"])

        avertissements = []
        if horloge_reculee:
            avertissements.append("La date de l'ordinateur est antérieure à la dernière "
                                  "utilisation : vérifie l'heure de Windows.")

        texte = self.repo.get("licence")
        licence = probleme = None
        if texte:
            try:
                licence = analyser_licence(texte, self.cle_publique, machine, reference)
            except ErreurLicence as e:
                probleme = str(e)

        if licence:
            restants = (licence.expire - reference).days if licence.expire else None
            if restants is not None and restants <= 30:
                avertissements.append(
                    "La licence expire aujourd'hui : contacte ton fournisseur pour la "
                    "renouveler." if restants == 0 else
                    f"La licence expire dans {restants} jour(s) : contacte ton fournisseur "
                    "pour la renouveler.")
            validite = (f"valable jusqu'au {_fr(licence.expire)}." if licence.expire
                        else "sans limite de durée.")
            return EtatLicence(
                mode="licence", message=f"Licence valide pour « {licence.ecole} » - {validite}",
                machine=machine, reference=reference, jours_restants=restants,
                ecole=licence.ecole, licence_id=licence.id,
                expire_le=licence.expire.isoformat() if licence.expire else None,
                avertissement=" ".join(avertissements) or None)

        restants = ESSAI_JOURS - (reference - debut).days
        if restants > 0 and not alteration:
            dernier_jour = debut + timedelta(days=ESSAI_JOURS - 1)
            message = (f"Version d'essai : {restants} jour(s) restant(s) "
                       f"(jusqu'au {_fr(dernier_jour)}).")
            if probleme:
                message += " " + probleme
            return EtatLicence(mode="essai", message=message, machine=machine,
                               reference=reference, jours_restants=restants,
                               probleme=probleme,
                               avertissement=" ".join(avertissements) or None)

        if alteration:
            raison = ("Les données de la période d'essai ont été altérées : l'essai est "
                      "terminé.")
        elif probleme:
            raison = ""
        else:
            raison = "La période d'essai est terminée."
        message = " ".join(p for p in (probleme, raison, "Active une licence pour reprendre "
                                       "la saisie : en attendant, l'application reste "
                                       "consultable.") if p)
        return EtatLicence(mode="expire", message=message, machine=machine,
                           reference=reference, jours_restants=0, probleme=probleme,
                           avertissement=" ".join(avertissements) or None)

    # --- Activation ------------------------------------------------------------------------
    def activer(self, texte) -> EtatLicence:
        if self.auth is not None and not self.auth.peut("licence.gerer"):
            raise ErreurMetier("Seul un administrateur peut activer une licence.")
        analyser_licence(texte, self.cle_publique, self.machine(), self.etat().reference)
        payload, signature = lire_cle(texte)
        self.repo.set("licence", construire_cle(payload, signature))
        self.repo.set("licence_activee_le", self._aujourdhui().isoformat())
        self._cache = None
        return self.etat()