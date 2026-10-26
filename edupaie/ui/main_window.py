from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from edupaie.ui.caisse_page import CaissePage
from edupaie.ui.dashboard_page import DashboardPage
from edupaie.ui.eleves_page import ElevesPage
from edupaie.ui.frais_page import FraisPage
from edupaie.ui.impayes_page import ImpayesPage
from edupaie.ui.mot_de_passe_dialog import MotDePasseDialog
from edupaie.ui.sauvegardes_page import SauvegardesPage
from edupaie.ui.utilisateurs_page import UtilisateursPage


class MainWindow(QMainWindow):
    def __init__(self, eleve_service, paiement_service, auth,
                 frais_service=None, sauvegarde_service=None, caisse_service=None,
                 remise_service=None, echeancier_service=None):
        super().__init__()
        self.deconnexion = False  # True si on se déconnecte ou se verrouille
        self.setWindowTitle("EduPaie - Gestion des paiements scolaires")

        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.pages = QStackedWidget()
        self._ajouter_page("Élèves", ElevesPage(
            eleve_service, paiement_service, auth, frais_service,
            remise_service, echeancier_service))
        self._ajouter_page("Tableau de bord", DashboardPage(paiement_service))
        if echeancier_service is not None and auth.peut("impayes.voir"):
            self._ajouter_page("Impayés", ImpayesPage(echeancier_service))
        if caisse_service is not None and auth.peut("caisse.voir"):
            self._ajouter_page("Clôture de caisse", CaissePage(caisse_service))
        if frais_service is not None and auth.peut("frais.gerer"):
            self._ajouter_page("Classes et frais",
                               FraisPage(frais_service, echeancier_service))
        if auth.peut("utilisateur.gerer"):
            self._ajouter_page("Utilisateurs", UtilisateursPage(auth))
        if sauvegarde_service is not None and auth.peut("sauvegarde.gerer"):
            self._ajouter_page("Sauvegardes", SauvegardesPage(sauvegarde_service))
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)

        marque = QLabel("EduPaie")
        marque.setObjectName("marque")

        btn_mdp = QPushButton("Mon mot de passe")
        btn_mdp.setObjectName("motdepasse")
        btn_mdp.clicked.connect(lambda: MotDePasseDialog(auth, self).exec())

        btn_deconnexion = QPushButton("Se déconnecter")
        btn_deconnexion.setObjectName("deconnexion")
        btn_deconnexion.clicked.connect(self.deconnecter)

        cote = QWidget()
        cote.setObjectName("cote")
        cote.setFixedWidth(190)
        colonne = QVBoxLayout(cote)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(marque)
        colonne.addWidget(self.menu, 1)
        colonne.addWidget(btn_mdp)
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