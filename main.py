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

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    conn = get_connection()
    eleves = EleveRepository(conn)
    paiements = PaiementRepository(conn)
    fenetre = MainWindow(EleveService(eleves), PaiementService(eleves, paiements))
    fenetre.resize(1180, 720)
    fenetre.showMaximized()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

