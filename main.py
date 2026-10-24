import os
import signal
import sqlite3
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from edupaie.db.connection import get_connection
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.eleve_service import EleveService
from edupaie.services.frais_service import FraisService
from edupaie.services.paiement_service import PaiementService
from edupaie.ui.inactivite import DetecteurInactivite
from edupaie.ui.login_dialog import LoginDialog
from edupaie.ui.main_window import MainWindow
from edupaie.ui.style import STYLE

DELAI_INACTIVITE_MS = 5 * 60 * 1000  # 5 minutes


def preparer_dossier_de_travail():
    """Version installée : base et reçus vont dans %LOCALAPPDATA%\\EduPaie."""
    if getattr(sys, "frozen", False):
        dossier = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EduPaie"
        dossier.mkdir(parents=True, exist_ok=True)
        os.chdir(dossier)


def initialiser_base():
    """Crée la base si besoin et ajoute les tables manquantes (sans rien effacer)."""
    Path("data").mkdir(exist_ok=True)
    ressources = Path(getattr(sys, "_MEIPASS", "."))
    schema = ressources / "data" / "schema.sql"
    conn = sqlite3.connect("data/edupaie.db")
    conn.executescript(schema.read_text(encoding="utf-8"))
    conn.close()


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

    sys.exit(0)


if __name__ == "__main__":
    main()