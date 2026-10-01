import sys

from PySide6.QtWidgets import QApplication

from edupaie.db.connection import get_connection
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.services.eleve_service import EleveService
from edupaie.ui.main_window import MainWindow
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.services.paiement_service import PaiementService


def main():
    app = QApplication(sys.argv)
    conn = get_connection()
    eleves = EleveRepository(conn)
    paiements = PaiementRepository(conn)
    fenetre = MainWindow(EleveService(eleves), PaiementService(eleves, paiements))
    fenetre.resize(1000, 600)
    fenetre.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()