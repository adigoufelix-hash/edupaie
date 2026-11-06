from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

from edupaie.services.ecole import courant
from edupaie.ui.animations import fondu_page
from edupaie.ui.annee_page import AnneePage
from edupaie.ui.caisse_page import CaissePage
from edupaie.ui.classes_page import ClassesPage
from edupaie.ui.dashboard_page import DashboardPage
from edupaie.ui.ecole_page import EcolePage
from edupaie.ui.eleves_page import ElevesPage
from edupaie.ui.frais_page import FraisPage
from edupaie.ui.guide_page import GuidePage
from edupaie.ui.impayes_page import ImpayesPage
from edupaie.ui.journal_page import JournalPage
from edupaie.ui.licence_page import LicencePage
from edupaie.ui.mot_de_passe_dialog import MotDePasseDialog
from edupaie.ui.sauvegardes_page import SauvegardesPage
from edupaie.ui.utilisateurs_page import UtilisateursPage
from edupaie.ui.verification_page import VerificationPage
from edupaie.ui.recouvrement_page import RecouvrementPage
from edupaie.ui.rapprochement_page import RapprochementPage


class MainWindow(QMainWindow):
    COULEURS_BANDEAU = {"licence": ("#fef3c7", "#92400e"), "essai": ("#ffedd5", "#9a3412"),
                        "expire": ("#fee2e2", "#991b1b")}

    def __init__(self, eleve_service, paiement_service, auth,
                 frais_service=None, sauvegarde_service=None, caisse_service=None,
                 remise_service=None, echeancier_service=None, ecole_service=None,
                 import_service=None, classe_service=None, journal_service=None,
                 verification_service=None, annee_service=None, licence_service=None,
                 guide_service=None, demarrage_service=None, resume_service=None,
                recouvrement_service=None, rapprochement_service=None):
        super().__init__()
        self.deconnexion = False  # True si on se déconnecte ou se verrouille
        nom_ecole = courant().nom
        self.setWindowTitle(f"{nom_ecole} - EduPaie" if nom_ecole
                            else "EduPaie - Gestion des paiements scolaires")

        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.pages = QStackedWidget()
        self._ajouter_page("Élèves", ElevesPage(
            eleve_service, paiement_service, auth, frais_service,
            remise_service, echeancier_service, import_service))
        self._ajouter_page("Tableau de bord", DashboardPage(paiement_service))
        if verification_service is not None and auth.peut("paiement.lire"):
            self._ajouter_page("Vérifier un reçu", VerificationPage(verification_service))
        if echeancier_service is not None and auth.peut("impayes.voir"):
            self._ajouter_page("Impayés", ImpayesPage(echeancier_service))
        if recouvrement_service is not None and auth.peut("recouvrement.voir"):
            self._ajouter_page("Recouvrement", RecouvrementPage(recouvrement_service))
        if rapprochement_service is not None and auth.peut("rapprochement.gerer"):
            self._ajouter_page("Rapprochement", RapprochementPage(rapprochement_service))
        if caisse_service is not None and auth.peut("caisse.voir"):
            self._ajouter_page("Caisse", CaissePage(caisse_service, resume_service=resume_service))
        if annee_service is not None and auth.peut("annee.gerer"):
            self._ajouter_page("Clôture de caisse",
                               CaissePage(caisse_service, resume_service=resume_service))
        if classe_service is not None and auth.peut("classe.gerer"):
            self._ajouter_page("Classes", ClassesPage(classe_service))
        if frais_service is not None and auth.peut("frais.gerer"):
            self._ajouter_page("Classes et frais",
                               FraisPage(frais_service, echeancier_service))
        if auth.peut("utilisateur.gerer"):
            self._ajouter_page("Utilisateurs", UtilisateursPage(auth))
        if journal_service is not None and auth.peut("audit.voir"):
            self._ajouter_page("Journal d'audit", JournalPage(journal_service))
        if sauvegarde_service is not None and auth.peut("sauvegarde.gerer"):
            self._ajouter_page("Sauvegardes", SauvegardesPage(sauvegarde_service))
        if licence_service is not None and auth.peut("licence.gerer"):
            self._ajouter_page("Licence", LicencePage(licence_service))
        if ecole_service is not None and auth.peut("ecole.gerer"):
            self._ajouter_page("Paramètres", EcolePage(ecole_service))
        if guide_service is not None:
            self._ajouter_page("Guide d'utilisation",
                               GuidePage(guide_service, demarrage_service, self._aller_a))
        self.menu.currentRowChanged.connect(self._changer_page)
        self.menu.setCurrentRow(0)
        if guide_service is not None and not nom_ecole and auth.peut("ecole.gerer"):
            self._aller_a("Guide d'utilisation")  # école neuve : on commence par le guide

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
        cote.setFixedWidth(230)
        colonne = QVBoxLayout(cote)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(marque)
        colonne.addWidget(self.menu, 1)
        colonne.addWidget(btn_mdp)
        colonne.addWidget(btn_deconnexion)

        droite = QWidget()
        colonne_droite = QVBoxLayout(droite)
        colonne_droite.setContentsMargins(0, 0, 0, 0)
        colonne_droite.setSpacing(0)
        colonne_droite.addWidget(self._construire_bandeau(licence_service, auth))
        colonne_droite.addWidget(self.pages, 1)

        centre = QWidget()
        mise_en_page = QHBoxLayout(centre)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)
        mise_en_page.addWidget(cote)
        mise_en_page.addWidget(droite, 1)
        self.pages.setContentsMargins(16, 16, 16, 16)
        self.setCentralWidget(centre)

        raccourci = QShortcut(QKeySequence("F1"), self)  # F1 : le guide, partout
        raccourci.activated.connect(lambda: self._aller_a("Guide d'utilisation"))

    def _construire_bandeau(self, licence_service, auth):
        """Bandeau d'état de la licence (masqué quand tout est en règle)."""
        bandeau = QFrame()
        bandeau.setObjectName("bandeau_licence")
        ligne = QHBoxLayout(bandeau)
        ligne.setContentsMargins(16, 8, 16, 8)
        texte = QLabel()
        texte.setWordWrap(True)
        bouton = QPushButton("Activer une licence")
        bouton.clicked.connect(lambda: self._aller_a("Licence"))
        bouton.setVisible(auth.peut("licence.gerer"))
        ligne.addWidget(texte, 1)
        ligne.addWidget(bouton)
        etat = licence_service.etat() if licence_service is not None else None
        if etat is None or (etat.mode == "licence" and not etat.avertissement):
            bandeau.hide()
            return bandeau
        if etat.mode == "licence":
            message = etat.avertissement
        else:
            message = etat.message + (" " + etat.avertissement if etat.avertissement else "")
            if etat.mode == "expire":
                message += " Mode consultation : la saisie est bloquée."
        fond, encre = self.COULEURS_BANDEAU[etat.mode]
        bandeau.setStyleSheet(f"QFrame#bandeau_licence {{ background: {fond}; }}")
        texte.setStyleSheet(f"color: {encre}; font-weight: bold; background: transparent;")
        texte.setText(message)
        return bandeau

    def _aller_a(self, titre) -> bool:
        """Ouvre l'écran du menu portant ce titre ; False s'il n'existe pas pour ce rôle."""
        for i in range(self.menu.count()):
            if self.menu.item(i).text() == titre:
                self.menu.setCurrentRow(i)
                return True
        return False

    def _ajouter_page(self, titre, widget):
        self.menu.addItem(titre)
        self.pages.addWidget(widget)

    def _changer_page(self, index):
        self.pages.setCurrentIndex(index)
        fondu_page(self.pages.currentWidget())

    def deconnecter(self):
        """Ferme la session : main.py réaffiche alors l'écran de connexion."""
        self.deconnexion = True
        QApplication.closeAllWindows()  # ferme aussi les dialogues ouverts