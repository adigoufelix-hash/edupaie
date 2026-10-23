from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from edupaie.ui.dashboard_page import DashboardPage
from edupaie.ui.eleves_page import ElevesPage
from edupaie.ui.utilisateurs_page import UtilisateursPage


class MainWindow(QMainWindow):
    def __init__(self, eleve_service, paiement_service, auth):
        super().__init__()
        self.deconnexion = False  # passe à True si on se déconnecte ou se verrouille
        self.setWindowTitle("EduPaie - Gestion des paiements scolaires")
        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.pages = QStackedWidget()
        self._ajouter_page("Élèves", ElevesPage(eleve_service, paiement_service, auth))
        self._ajouter_page("Tableau de bord", DashboardPage(paiement_service))
        if auth.peut("utilisateur.gerer"):
            self._ajouter_page("Utilisateurs", UtilisateursPage(auth))
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)

        marque = QLabel("EduPaie")
        marque.setObjectName("marque")

        btn_deconnexion = QPushButton("Se déconnecter")
        btn_deconnexion.setObjectName("deconnexion")
        btn_deconnexion.setStyleSheet(
            "background:#c0392b; color:white; font-weight:bold; padding:10px; border:none;"
        )
        btn_deconnexion.clicked.connect(self.deconnecter)
        cote = QWidget()
        cote.setObjectName("cote")
        cote.setFixedWidth(190)
        colonne = QVBoxLayout(cote)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(marque)
        colonne.addWidget(self.menu, 1)
        colonne.addWidget(btn_deconnexion)

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

    def deconnecter(self):
        """Ferme la session : main.py réaffiche alors l'écran de connexion."""
        self.deconnexion = True
        QApplication.closeAllWindows()  # ferme aussi les dialogues ouverts