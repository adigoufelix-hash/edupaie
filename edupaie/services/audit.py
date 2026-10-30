import inspect
import sys
from collections import namedtuple
from datetime import datetime

from edupaie.repositories.audit_repository import HASH_INITIAL, calculer_hash
from edupaie.services.paiement_service import ErreurMetier

LIMITE = 2000

LIBELLES = {
    "connexion": "Connexion",
    "echec_connexion": "Échec de connexion",
    "blocage_connexion": "Compte bloqué (trop d'échecs)",
    "eleve.creation": "Élève créé",
    "eleve.modification": "Élève modifié",
    "eleve.suppression": "Élève supprimé",
    "eleve.import": "Import d'élèves",
    "contact.modification": "Contact du parent modifié",
    "classe.ajout": "Classe ajoutée",
    "classe.renommage": "Classe renommée",
    "classe.suppression": "Classe supprimée",
    "paiement.enregistrement": "Paiement enregistré",
    "paiement.annulation": "Paiement annulé",
    "remise.accordee": "Remise accordée",
    "remise.annulee": "Remise annulée",
    "frais.ajout": "Frais : ligne ajoutée",
    "frais.modification": "Frais : ligne modifiée",
    "frais.suppression": "Frais : ligne supprimée",
    "frais.copie": "Frais copiés vers une autre classe",
    "echeancier.ajout": "Échéancier : tranche ajoutée",
    "echeancier.modification": "Échéancier : tranche modifiée",
    "echeancier.suppression": "Échéancier : tranche supprimée",
    "echeancier.copie": "Échéancier copié vers une autre classe",
    "utilisateur.creation": "Compte créé",
    "utilisateur.suppression": "Compte supprimé",
    "utilisateur.mdp_reinitialise": "Mot de passe réinitialisé",
    "utilisateur.mdp_change": "Mot de passe modifié",
    "utilisateur.codes_secours": "Codes de secours générés",
    "utilisateur.recuperation": "Mot de passe récupéré (code de secours)",
    "utilisateur.recuperation_echec": "Échec de récupération de mot de passe",
    "recu.alerte": "Reçu douteux présenté",
    "sauvegarde.manuelle": "Sauvegarde manuelle",
    "sauvegarde.restauration": "Sauvegarde restaurée",
    "ecole.modification": "Paramètres de l'école modifiés",
}

CATEGORIES = {
    "Connexions": ("connexion", "echec_connexion", "blocage_connexion"),
    "Élèves": ("eleve.%", "contact.%", "classe.%"),
    "Paiements": ("paiement.%",),
    "Remises": ("remise.%",),
    "Frais et échéancier": ("frais.%", "echeancier.%"),
    "Utilisateurs": ("utilisateur.%",),
    "Reçus": ("recu.%",),
    "Système": ("sauvegarde.%", "ecole.%"),
}

# Événements mis en évidence (en rouge) dans l'écran du journal
SENSIBLES = {
    "echec_connexion", "blocage_connexion", "eleve.suppression", "paiement.annulation",
    "remise.annulee", "utilisateur.suppression", "utilisateur.mdp_reinitialise",
    "sauvegarde.restauration", "recu.alerte","utilisateur.recuperation", "utilisateur.recuperation_echec",
}

# apres(service, arguments, resultat, avant) -> dict ou None
# avant(service, arguments) -> contexte (état avant l'action)
# erreur(service, arguments, exception) -> dict ou None
Regle = namedtuple("Regle", "apres avant erreur", defaults=(None, None))


class Audite:
    """Enveloppe un service : journalise ses méthodes après leur réussite.
    Le service enveloppé n'est pas modifié ; les autres méthodes passent telles quelles."""

    def __init__(self, service, journal, regles):
        self._service = service
        self._journal = journal
        self._regles = regles

    def __getattr__(self, nom):
        attribut = getattr(self._service, nom)
        regle = self._regles.get(nom)
        if regle is None or not callable(attribut):
            return attribut
        return self._envelopper(attribut, regle)

    @staticmethod
    def _proteger(fonction):
        try:
            return fonction()
        except Exception:
            return None

    def _ecrire(self, fabrique):
        try:
            entree = fabrique()
            if entree:
                self._journal.journaliser(**entree)
        except Exception as e:  # le journal ne doit jamais bloquer le travail
            print("Journal d'audit : écriture impossible :", e, file=sys.stderr)

    def _envelopper(self, methode, regle):
        def appel(*args, **kwargs):
            try:
                liaison = inspect.signature(methode).bind(*args, **kwargs)
                liaison.apply_defaults()
                arguments = dict(liaison.arguments)
            except TypeError:
                return methode(*args, **kwargs)  # mauvais appel : Python lève l'erreur
            avant = (self._proteger(lambda: regle.avant(self._service, arguments))
                     if regle.avant else None)
            try:
                resultat = methode(*args, **kwargs)
            except ErreurMetier as e:
                if regle.erreur:
                    self._ecrire(lambda exc=e: regle.erreur(self._service, arguments, exc))
                raise
            self._ecrire(lambda: regle.apres(self._service, arguments, resultat, avant))
            return resultat
        return appel


class JournalService:
    def __init__(self, repo, auth=None, maintenant=datetime.now):
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits
        self.maintenant = maintenant

    def _exiger(self):
        if self.auth is not None and not self.auth.peut("audit.voir"):
            raise ErreurMetier("Le journal d'audit est réservé à l'administrateur.")

    def journaliser(self, action, detail="", objet=None, objet_id=None, acteur=None):
        """acteur : (id, nom) ; par défaut l'utilisateur connecté."""
        if acteur is None:
            utilisateur = self.auth.utilisateur if self.auth is not None else None
            acteur = ((utilisateur["id"], utilisateur["nom_complet"])
                      if utilisateur else (None, None))
        self.repo.ajouter(self.maintenant().isoformat(timespec="seconds"),
                          acteur[0], acteur[1], action, objet, objet_id,
                          str(detail)[:500])

    @staticmethod
    def categories() -> list[str]:
        return list(CATEGORIES)

    @staticmethod
    def _date(valeur) -> str:
        try:
            return datetime.strptime(str(valeur).strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ErreurMetier("Date invalide (format attendu : AAAA-MM-JJ).") from None

    def utilisateurs(self) -> list[str]:
        self._exiger()
        return self.repo.utilisateurs()

    def consulter(self, debut, fin, categorie=None, utilisateur=None, recherche="",
                  limite=LIMITE):
        self._exiger()
        debut, fin = self._date(debut), self._date(fin)
        if debut > fin:
            raise ErreurMetier("La date de début doit précéder la date de fin.")
        return self.repo.lister(debut, fin, CATEGORIES.get(categorie),
                                utilisateur or None, str(recherche or "").strip(), limite)

    def verifier(self) -> dict:
        """Contrôle la chaîne d'empreintes : détecte toute ligne modifiée ou supprimée."""
        self._exiger()
        precedent, nb, attendu, derniere = HASH_INITIAL, 0, 1, 0
        for ligne in self.repo.tout():
            if ligne["id"] != attendu:
                return {"ok": False, "nb": nb, "message":
                        f"L'événement n°{attendu} est manquant : le journal a été altéré."}
            empreinte = calculer_hash(
                precedent, ligne["date_heure"], ligne["utilisateur_id"],
                ligne["utilisateur"], ligne["action"], ligne["objet"],
                ligne["objet_id"], ligne["detail"])
            if empreinte != ligne["hash"]:
                return {"ok": False, "nb": nb, "message":
                        f"L'événement n°{ligne['id']} ({ligne['date_heure']}) a été "
                        "modifié : le journal a été altéré."}
            precedent, nb = ligne["hash"], nb + 1
            derniere = ligne["id"]
            attendu = ligne["id"] + 1
        sequence = self.repo.sequence()
        if sequence is not None and sequence > derniere:
            return {"ok": False, "nb": nb, "message":
                    "Des événements ont été supprimés à la fin du journal : "
                    "le journal a été altéré."}
        return {"ok": True, "nb": nb, "message": "Journal intact."}