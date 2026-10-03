from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QMainWindow,
                               QStackedWidget, QVBoxLayout, QWidget)

from edupaie.ui.dashboard_page import DashboardPage
from edupaie.ui.eleves_page import ElevesPage


class MainWindow(QMainWindow):
    def __init__(self, eleve_service, paiement_service):
        super().__init__()
        self.setWindowTitle("EduPaie - Gestion des paiements scolaires")
        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.pages = QStackedWidget()
        self._ajouter_page("Élèves", ElevesPage(eleve_service, paiement_service))
        self._ajouter_page("Tableau de bord", DashboardPage(paiement_service))
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)

        marque = QLabel("EduPaie")
        marque.setObjectName("marque")
        cote = QWidget()
        cote.setObjectName("cote")
        cote.setFixedWidth(210)
        colonne = QVBoxLayout(cote)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(marque)
        colonne.addWidget(self.menu, 1)

        centre = QWidget()
        mise_en_page = QHBoxLayout(centre)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)
        mise_en_page.addWidget(cote)
        mise_en_page.addWidget(self.pages, 1)
        self.pages.setContentsMargins(16, 16, 16, 16)
        self.setCentralWidget(centre)

    def _ajouter_page(self, titre, widget):
        self.menu.addItem(titre)
        self.pages.addWidget(widget)