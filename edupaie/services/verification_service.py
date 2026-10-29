import hmac
import secrets

from edupaie.services import verification
from edupaie.services.paiement_service import ErreurMetier

MESSAGES = {
    "authentique": "Ce reçu existe et son code de contrôle est valide.",
    "annule": "Ce reçu a été annulé : il ne vaut plus preuve de paiement.",
    "falsifie": ("Le code de contrôle ne correspond pas aux données enregistrées : reçu "
                 "falsifié, code mal saisi, ou enregistrement modifié. Ne l'accepte pas "
                 "avant d'avoir vérifié."),
    "non_controle": ("Ce reçu existe, mais aucun code de contrôle n'a été fourni. "
                     "Compare les informations ci-dessous avec le papier, ou scanne le QR code."),
    "introuvable": "Aucun reçu portant ce numéro dans cette base.",
    "invalide": ("Saisie illisible. Scanne le QR code du reçu, ou tape le numéro "
                 "(exemple : REC-2026-000001) suivi du code."),
}


class VerificationService:
    def __init__(self, repo, auth=None):
        self.repo = repo
        self.auth = auth  # None dans les tests

    def cle(self) -> str:
        """Clé de l'installation : créée une seule fois, conservée dans la base."""
        cle = self.repo.get_parametre("cle_recus")
        if not cle:
            cle = secrets.token_hex(32)
            self.repo.set_parametre("cle_recus", cle)
        return cle

    def verifier(self, saisie) -> dict:
        if self.auth is not None and not self.auth.peut("paiement.lire"):
            raise ErreurMetier("Votre rôle ne permet pas de vérifier les reçus.")
        numero, code = verification.lire_saisie(saisie)
        if numero is None:
            return self._reponse("invalide")
        ligne = self.repo.trouver_recu(numero)
        if ligne is None:
            return self._reponse("introuvable")
        details = {
            "numero": ligne["numero_recu"], "eleve": f"{ligne['nom']} {ligne['prenom']}",
            "classe": ligne["classe"], "montant": ligne["montant"],
            "date": ligne["date_paiement"], "mode": ligne["mode"],
            "encaisse_par": ligne["encaisse_par"], "annule": bool(ligne["annule"]),
            "motif_annulation": ligne["motif_annulation"],
            "annule_par": ligne["annule_par"], "annule_le": ligne["annule_le"],
        }
        if ligne["annule"]:
            return self._reponse("annule", details)
        if code is None:
            return self._reponse("non_controle", details)
        attendu = verification.calculer_code(
            self.cle(), ligne["numero_recu"], ligne["montant"], ligne["date_paiement"],
            ligne["mode"], ligne["eleve_id"])
        statut = "authentique" if hmac.compare_digest(code, attendu) else "falsifie"
        return self._reponse(statut, details)

    @staticmethod
    def _reponse(statut, details=None) -> dict:
        return {"statut": statut, "message": MESSAGES[statut], "details": details}