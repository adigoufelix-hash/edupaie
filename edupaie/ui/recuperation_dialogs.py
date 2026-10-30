import tempfile
from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QVBoxLayout)

from edupaie.services.codes_pdf import generer_codes_pdf
from edupaie.services.paiement_service import ErreurMetier


def _champ_mot_de_passe() -> QLineEdit:
    champ = QLineEdit()
    champ.setEchoMode(QLineEdit.EchoMode.Password)
    return champ


class ChangementObligatoireDialog(QDialog):
    """Après un mot de passe temporaire : choix du mot de passe personnel."""

    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Choisis ton mot de passe")
        self.setMinimumWidth(440)
        info = QLabel(
            "Ton mot de passe a été défini par un administrateur. Choisis maintenant un "
            "mot de passe personnel (8 caractères minimum, avec une lettre et un chiffre).")
        info.setWordWrap(True)
        self.nouveau = _champ_mot_de_passe()
        self.confirmation = _champ_mot_de_passe()
        form = QFormLayout(self)
        form.addRow(info)
        form.addRow("Nouveau mot de passe", self.nouveau)
        form.addRow("Confirmation", self.confirmation)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        if self.nouveau.text() != self.confirmation.text():
            QMessageBox.warning(self, "Données invalides",
                                "Les deux mots de passe ne correspondent pas.")
            return
        try:
            self.auth.definir_mon_mot_de_passe(self.nouveau.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()


class RecuperationDialog(QDialog):
    """Mot de passe oublié : récupération d'un compte administrateur avec un code de secours."""

    def __init__(self, auth, login="", parent=None):
        super().__init__(parent)
        self.auth = auth
        self.login_saisi = ""
        self.setWindowTitle("Mot de passe oublié")
        self.setMinimumWidth(480)
        info = QLabel(
            "Réservé aux administrateurs : saisis ton identifiant et l'un des codes de "
            "secours de ta feuille imprimée. Si tu n'es pas administrateur, demande à un "
            "administrateur de réinitialiser ton mot de passe.")
        info.setWordWrap(True)
        self.login = QLineEdit(login)
        self.code = QLineEdit()
        self.code.setPlaceholderText("Ex. : K7M2P-9XQ4R")
        self.nouveau = _champ_mot_de_passe()
        self.confirmation = _champ_mot_de_passe()
        form = QFormLayout(self)
        form.addRow(info)
        form.addRow("Identifiant", self.login)
        form.addRow("Code de secours", self.code)
        form.addRow("Nouveau mot de passe", self.nouveau)
        form.addRow("Confirmation", self.confirmation)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        if self.nouveau.text() != self.confirmation.text():
            QMessageBox.warning(self, "Données invalides",
                                "Les deux mots de passe ne correspondent pas.")
            return
        try:
            restants = self.auth.reinitialiser_avec_code(
                self.login.text(), self.code.text(), self.nouveau.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Récupération impossible", str(e))
            return
        message = "Mot de passe modifié. Tu peux te connecter."
        if restants == 0:
            message += ("\n\nIl ne te reste plus aucun code de secours : génère-en de "
                        "nouveaux dès que tu es connecté (écran « Utilisateurs »).")
        else:
            message += f"\n\nCodes de secours restants : {restants}."
        QMessageBox.information(self, "Récupération réussie", message)
        self.login_saisi = self.login.text().strip().lower()
        self.accept()


class CodesSecoursDialog(QDialog):
    """Affiche les codes de secours une seule fois."""

    def __init__(self, codes, nom_utilisateur, parent=None):
        super().__init__(parent)
        self.codes = list(codes)
        self.nom_utilisateur = nom_utilisateur
        self.confirme = False
        self.setWindowTitle("Codes de secours")
        self.setMinimumWidth(500)

        consigne = QLabel(
            "<b>Note ces codes maintenant : ils ne seront plus jamais affichés.</b><br>"
            "Chaque code permet de créer un nouveau mot de passe pour le compte "
            f"<b>{escape(nom_utilisateur)}</b>, une seule fois (écran de connexion, "
            "« Mot de passe oublié ? »).<br>Conserve la feuille dans un endroit sûr et "
            "fermé, jamais à côté de l'ordinateur.")
        consigne.setWordWrap(True)
        liste = QLabel("<pre style='font-size:18px; font-weight:bold'>"
                       + "\n".join(f"{i}. {c}" for i, c in enumerate(self.codes, start=1))
                       + "</pre>")
        liste.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pdf = QPushButton("Imprimer la feuille (PDF)")
        pdf.clicked.connect(self._pdf)
        self.case = QCheckBox("J'ai conservé ces codes dans un endroit sûr")
        self.terminer = QPushButton("Terminer")
        self.terminer.setEnabled(False)
        self.case.toggled.connect(self.terminer.setEnabled)
        self.terminer.clicked.connect(self._terminer)

        bas = QHBoxLayout()
        bas.addWidget(pdf)
        bas.addStretch()
        bas.addWidget(self.terminer)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(consigne)
        mise_en_page.addWidget(liste)
        mise_en_page.addWidget(self.case)
        mise_en_page.addLayout(bas)

    def _pdf(self):
        try:
            chemin = generer_codes_pdf(self.codes, self.nom_utilisateur,
                                       tempfile.gettempdir())
        except OSError as e:
            QMessageBox.warning(self, "Feuille impossible", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin.resolve())))
        QMessageBox.information(
            self, "Feuille générée",
            "Imprime la feuille, puis supprime le fichier PDF de l'ordinateur "
            "(il est dans le dossier temporaire).")

    def _terminer(self):
        self.confirme = True
        self.accept()

    def reject(self):
        if not self.confirme and QMessageBox.question(
                self, "Codes de secours",
                "Les codes ne seront plus jamais affichés. Fermer sans les avoir "
                "conservés ?", QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        super().reject()