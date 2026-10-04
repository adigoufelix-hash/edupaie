import os
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from edupaie.services.recu_pdf import generer_recu_pdf


def ouvrir_recu(parent, service, paiement_id):
    """Génère (ou rouvre) le reçu PDF d'un paiement puis l'ouvre."""
    dossier = Path.home() / "EduPaie" / "recus"
    try:
        eleve, paiement = service.recu(paiement_id)
        try:
            chemin = generer_recu_pdf(eleve, paiement, dossier)
        except PermissionError:
            # PDF déjà ouvert dans le lecteur : il est identique, on le rouvre
            chemin = dossier / f"{paiement.numero_recu}.pdf"
            if not chemin.exists():
                raise
        os.startfile(chemin)
    except Exception as e:
        QMessageBox.warning(parent, "Reçu indisponible",
                            f"Impossible d'ouvrir le reçu : {e}")