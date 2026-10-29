import tempfile

from PySide6.QtCore import QBuffer, QIODevice, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (QColorDialog, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from edupaie.models.entities import Eleve, Paiement
from edupaie.services import couleurs
from edupaie.services.ecole import ParametresEcole
from edupaie.services.ecole_service import GARDER
from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.recu_pdf import generer_recu_pdf
from edupaie.ui import theme

PROPOSITIONS = [
    ("Indigo (couleur d'origine)", "#4F46E5"), ("Bleu", "#1D4ED8"),
    ("Vert", "#15803D"), ("Bordeaux", "#9F1239"), ("Orange", "#C2410C"),
    ("Violet", "#7E22CE"), ("Turquoise", "#0F766E"), ("Ardoise", "#334155"),
]


class EcolePage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        parametres = service.lire()
        self._logo = parametres.logo
        self._logo_change = False
        self._couleur = parametres.couleur
        self._couleur_change = False

        self.nom = QLineEdit(parametres.nom)
        self.nom.setPlaceholderText("Ex. : Collège Saint-Joseph de Lomé")
        self.adresse = QLineEdit(parametres.adresse)
        self.adresse.setPlaceholderText("Ex. : Rue des Écoles, Lomé")
        self.telephone = QLineEdit(parametres.telephone)
        self.telephone.setPlaceholderText("Ex. : +228 90 12 34 56")
        self.email = QLineEdit(parametres.email)
        self.email.setPlaceholderText("Ex. : contact@monecole.tg")

        self.logo = QLabel()
        self.logo.setFixedSize(120, 120)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setStyleSheet(
            "border: 1px dashed #9ca3af; border-radius: 8px; background: white;")
        choisir = QPushButton("Choisir un logo...")
        retirer = QPushButton("Retirer le logo")
        choisir.clicked.connect(self._choisir_logo)
        retirer.clicked.connect(self._retirer_logo)

        # Couleur de l'école
        pastilles = QHBoxLayout()
        for nom, code in PROPOSITIONS:
            bouton = QPushButton()
            bouton.setToolTip(nom)
            bouton.setFixedSize(30, 30)
            bouton.setStyleSheet(
                f"QPushButton {{ background: {code}; border: 2px solid white; "
                "border-radius: 15px; min-width: 26px; padding: 0; } "
                "QPushButton:hover { border: 2px solid #111827; }")
            bouton.clicked.connect(lambda _=False, c=code: self._definir_couleur(c))
            pastilles.addWidget(bouton)
        autre = QPushButton("Autre couleur...")
        origine = QPushButton("Couleur d'origine")
        autre.clicked.connect(self._autre_couleur)
        origine.clicked.connect(lambda: self._definir_couleur(""))
        pastilles.addWidget(autre)
        pastilles.addWidget(origine)
        pastilles.addStretch()
        self.etat_couleur = QLabel()
        self.etat_couleur.setTextFormat(Qt.TextFormat.RichText)
        self.etat_couleur.setWordWrap(True)

        apercu = QPushButton("Aperçu du reçu")
        enregistrer = QPushButton("Enregistrer")
        apercu.clicked.connect(self._apercu)
        enregistrer.clicked.connect(self._enregistrer)

        titre = QLabel("<h3 style='margin:0'>Paramètres de l'école</h3>")
        aide = QLabel(
            "Ces informations apparaissent en haut des reçus, de la clôture de caisse "
            "et de la liste des impayés. Le logo est réduit automatiquement. "
            "La couleur change aussitôt l'application : clique sur Enregistrer pour la garder.")
        aide.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Nom de l'école", self.nom)
        form.addRow("Adresse", self.adresse)
        form.addRow("Téléphone", self.telephone)
        form.addRow("E-mail", self.email)
        boutons_logo = QVBoxLayout()
        boutons_logo.addWidget(choisir)
        boutons_logo.addWidget(retirer)
        boutons_logo.addStretch()
        ligne_logo = QHBoxLayout()
        ligne_logo.addWidget(self.logo)
        ligne_logo.addLayout(boutons_logo)
        ligne_logo.addStretch()
        form.addRow("Logo", ligne_logo)
        colonne_couleur = QVBoxLayout()
        colonne_couleur.addLayout(pastilles)
        colonne_couleur.addWidget(self.etat_couleur)
        form.addRow("Couleur", colonne_couleur)

        bas = QHBoxLayout()
        bas.addWidget(apercu)
        bas.addStretch()
        bas.addWidget(enregistrer)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(titre)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(form)
        mise_en_page.addStretch()
        mise_en_page.addLayout(bas)
        self._afficher_logo()
        self._maj_couleur()

    # --- Logo --------------------------------------------------------------------
    def _afficher_logo(self):
        if self._logo:
            image = QImage.fromData(self._logo)
            if not image.isNull():
                self.logo.setPixmap(QPixmap.fromImage(image).scaled(
                    112, 112, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                return
        self.logo.clear()
        self.logo.setText("Aucun logo")

    def _choisir_logo(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir le logo", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not chemin:
            return
        image = QImage(chemin)
        if image.isNull():
            QMessageBox.warning(self, "Logo", "Ce fichier n'est pas une image lisible.")
            return
        if max(image.width(), image.height()) > 400:
            image = image.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        tampon = QBuffer()
        tampon.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(tampon, "PNG")
        self._logo = bytes(tampon.data())
        self._logo_change = True
        self._afficher_logo()

    def _retirer_logo(self):
        self._logo = None
        self._logo_change = True
        self._afficher_logo()

    # --- Couleur -----------------------------------------------------------------
    def _maj_couleur(self):
        if not self._couleur:
            self.etat_couleur.setText("Couleur d'origine d'EduPaie.")
            return
        ajustee, modifiee = couleurs.ajuster_principale(self._couleur)
        texte = f"Couleur choisie : <b>{self._couleur}</b>"
        if modifiee:
            texte += (f" - assombrie en <b>{ajustee}</b> pour que le texte blanc reste "
                      "lisible.")
        self.etat_couleur.setText(texte)

    def _definir_couleur(self, code):
        self._couleur = couleurs.normaliser(code) or ""
        self._couleur_change = True
        theme.appliquer(self._couleur)  # aperçu en direct sur toute l'application
        self._maj_couleur()

    def _autre_couleur(self):
        choix = QColorDialog.getColor(
            QColor(self._couleur or "#4F46E5"), self, "Couleur de l'école")
        if choix.isValid():
            self._definir_couleur(choix.name())

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._couleur_change:  # aperçu non enregistré : retour à la couleur enregistrée
            self._couleur_change = False
            self._couleur = self.service.lire().couleur
            theme.appliquer(self._couleur)
            self._maj_couleur()

    # --- Enregistrement et aperçu ------------------------------------------------------
    def _enregistrer(self):
        try:
            self.service.enregistrer(
                self.nom.text(), self.adresse.text(), self.telephone.text(),
                self.email.text(),
                logo=self._logo if self._logo_change else GARDER,
                couleur=self._couleur if self._couleur_change else GARDER)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self._logo_change = False
        self._couleur_change = False
        nom = self.service.lire().nom
        self.window().setWindowTitle(
            f"{nom} - EduPaie" if nom else "EduPaie - Gestion des paiements scolaires")
        QMessageBox.information(
            self, "Paramètres", "Enregistré. Les prochains PDF utiliseront ces informations.")

    def _apercu(self):
        parametres = ParametresEcole(
            " ".join(self.nom.text().split()), self.adresse.text().strip(),
            self.telephone.text().strip(), self.email.text().strip(), self._logo,
            self._couleur)
        eleve = Eleve(None, "Kouassi", "Kofi", "6e A", "2026-2027", 100000)
        paiement = Paiement(
            id=1, eleve_id=1, numero_recu="REC-0000-000000", montant=40000,
            date_paiement="2026-10-26", mode="especes", solde_apres=60000,
            encaisse_par="Exemple")
        try:
            chemin = generer_recu_pdf(eleve, paiement, tempfile.gettempdir(), parametres)
        except OSError as e:
            QMessageBox.warning(self, "Aperçu impossible", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin.resolve())))