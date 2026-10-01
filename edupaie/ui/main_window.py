from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QMainWindow,
                               QStackedWidget, QWidget)

from edupaie.ui.eleves_page import ElevesPage


class MainWindow(QMainWindow):
    def __init__(self, eleve_service, paiement_service):
        super().__init__()
        self.setWindowTitle("EduPaie - Gestion des paiements scolaires")
        self.menu = QListWidget()
        self.menu.setMaximumWidth(180)
        self.pages = QStackedWidget()
        self._ajouter_page("Élèves", ElevesPage(eleve_service, paiement_service))
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)
        centre = QWidget()
        mise_en_page = QHBoxLayout(centre)
        mise_en_page.addWidget(self.menu)
        mise_en_page.addWidget(self.pages, 1)
        self.setCentralWidget(centre)

    def _ajouter_page(self, titre, widget):
        self.menu.addItem(titre)
        self.pages.addWidget(widget)