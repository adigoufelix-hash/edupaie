import os
import runpy
import sys

from PySide6.QtWidgets import QApplication, QDialog

from edupaie.db.connection import get_connection
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.eleve_service import EleveService
from edupaie.services.paiement_service import PaiementService
from edupaie.ui.inactivite import DetecteurInactivite
from edupaie.ui.login_dialog import LoginDialog
from edupaie.ui.main_window import MainWindow
from edupaie.ui.style import STYLE

DELAI_INACTIVITE_MS = 5 * 60 * 1000  # 5 minutes


def main():
    if not os.path.exists("data/edupaie.db"):
        os.makedirs("data", exist_ok=True)
        runpy.run_path("creer_base.py", run_name="__main__")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    conn = get_connection()
    eleves = EleveRepository(conn)
    paiements = PaiementRepository(conn)

    auth = AuthService(UtilisateurRepository(conn))

    # Connexion obligatoire, répétée après chaque déconnexion ou verrouillage
    while True:
        if LoginDialog(auth).exec() != QDialog.Accepted:
            break

        fenetre = MainWindow(EleveService(eleves), PaiementService(eleves, paiements), auth)
        fenetre.resize(1180, 720)
        fenetre.showMaximized()

        detecteur = DetecteurInactivite(DELAI_INACTIVITE_MS, fenetre.deconnecter)
        app.installEventFilter(detecteur)

        app.exec()

        app.removeEventFilter(detecteur)
        detecteur.arreter()
        auth.deconnecter()
        if not fenetre.deconnexion:  # fenêtre fermée normalement : on quitte
            break

    sys.exit(0)


if __name__ == "__main__":
    main()