import os
import signal
import sys

from PySide6.QtWidgets import QApplication, QDialog
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.services.remise_service import RemiseService
from edupaie.db.connection import dossier_donnees, get_connection, initialiser_base
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.eleve_service import EleveService
from edupaie.services.frais_service import FraisService
from edupaie.services.paiement_service import PaiementService
from edupaie.services.sauvegarde_service import SauvegardeService
from edupaie.ui.inactivite import DetecteurInactivite
from edupaie.ui.login_dialog import LoginDialog
from edupaie.ui.main_window import MainWindow
from edupaie.ui.style import STYLE
from edupaie.services.caisse_service import CaisseService
DELAI_INACTIVITE_MS = 5 * 60 * 1000  # 5 minutes


def preparer_dossier_de_travail():
    """Version installée : reçus et données vont dans %LOCALAPPDATA%\\EduPaie."""
    if getattr(sys, "frozen", False):
        dossier = dossier_donnees()
        dossier.mkdir(parents=True, exist_ok=True)
        os.chdir(dossier)


def sauvegarder_sans_bloquer(service):
    """Une sauvegarde ratée ne doit jamais empêcher d'ouvrir ou de fermer l'application."""
    try:
        service.sauvegarde_auto()
    except Exception as e:
        print("Sauvegarde automatique impossible :", e, file=sys.stderr)


def main():
    preparer_dossier_de_travail()
    initialiser_base()

    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    conn = get_connection()
    eleves = EleveRepository(conn)
    paiements = PaiementRepository(conn)

    auth = AuthService(UtilisateurRepository(conn))
    frais = FraisService(FraisRepository(conn), auth)
    sauvegarde = SauvegardeService(auth)
    caisse = CaisseService(paiements, auth)
    remises = RemiseService(RemiseRepository(conn), eleves, paiements, auth)
    sauvegarder_sans_bloquer(sauvegarde)  # au lancement

    # Connexion obligatoire, répétée après chaque déconnexion ou verrouillage
    while True:
        login = LoginDialog(auth)
        login.show()
        login.raise_()
        login.activateWindow()
        if login.exec() != QDialog.Accepted:
            break

        fenetre = MainWindow(
            EleveService(eleves),
            PaiementService(eleves, paiements, auth),
            auth,
            frais,
            sauvegarde,
            caisse,
            remises,
        )
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

    sauvegarder_sans_bloquer(sauvegarde)  # à la fermeture
    sys.exit(0)


if __name__ == "__main__":
    main()