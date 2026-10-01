import sys

from PySide6.QtWidgets import QApplication

from edupaie.db.connection import get_connection
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.services.eleve_service import EleveService
from edupaie.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    fenetre = MainWindow(EleveService(EleveRepository(get_connection())))
    fenetre.resize(1000, 600)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()