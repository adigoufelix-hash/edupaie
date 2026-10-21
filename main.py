import sys
from PySide6.QtWidgets import QApplication
from pathlib import Path



from edupaie.db.connection import get_connection
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.services.eleve_service import EleveService
from edupaie.ui.main_window import MainWindow
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.services.paiement_service import PaiementService
from edupaie.ui.style import STYLE
from PySide6.QtWidgets import QApplication, QDialog
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.ui.login_dialog import LoginDialog

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    conn = get_connection()
    auth = AuthService(UtilisateurRepository(conn))
    if LoginDialog(auth).exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    eleves = EleveRepository(conn)
    paiements = PaiementRepository(conn)
    fenetre = MainWindow(EleveService(eleves), PaiementService(eleves, paiements))
    fenetre.resize(1180, 720)
    fenetre.showMaximized()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

