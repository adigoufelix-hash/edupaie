from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QInputDialog, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.permissions import ROLES
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.style import preparer_table


class UtilisateurDialog(QDialog):
    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Nouvel utilisateur")
        self.login = QLineEdit()
        self.nom = QLineEdit()
        self.role = QComboBox()
        self.role.addItems(ROLES)
        self.mdp = QLineEdit()
        self.mdp.setEchoMode(QLineEdit.EchoMode.Password)
        self.mdp2 = QLineEdit()
        self.mdp2.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout(self)
        form.addRow("Identifiant", self.login)
        form.addRow("Nom complet", self.nom)
        form.addRow("Rôle", self.role)
        form.addRow("Mot de passe", self.mdp)
        form.addRow("Confirmation", self.mdp2)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        if self.mdp.text() != self.mdp2.text():
            QMessageBox.warning(self, "Données invalides",
                                "Les deux mots de passe ne correspondent pas.")
            return
        try:
            self.auth.creer_utilisateur(
                self.login.text(), self.nom.text(), self.mdp.text(),
                self.role.currentText())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()


class UtilisateursPage(QWidget):
    def __init__(self, auth):
        super().__init__()
        self.auth = auth
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Identifiant", "Nom complet", "Rôle"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        ajouter = QPushButton("Ajouter un utilisateur")
        reinit = QPushButton("Réinitialiser le mot de passe")
        supprimer = QPushButton("Supprimer")
        supprimer.setObjectName("danger")
        ajouter.clicked.connect(self._ajouter)
        reinit.clicked.connect(self._reinitialiser)
        supprimer.clicked.connect(self._supprimer)

        bas = QHBoxLayout()
        for b in (ajouter, reinit, supprimer):
            bas.addWidget(b)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(bas)
        self.recharger()

    def recharger(self):
        try:
            lignes = self.auth.lister_utilisateurs()
        except ErreurMetier as e:
            QMessageBox.warning(self, "Accès refusé", str(e))
            return
        self.table.setRowCount(len(lignes))
        for i, ligne in enumerate(lignes):
            for col, cle in enumerate(("login", "nom_complet", "role")):
                self.table.setItem(i, col, QTableWidgetItem(str(ligne[cle])))
            self.table.item(i, 0).setData(Qt.UserRole, ligne["id"])

    def _selection(self):
        i = self.table.currentRow()
        if i < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord un utilisateur.")
            return None
        return self.table.item(i, 0).data(Qt.UserRole), self.table.item(i, 0).text()

    def _ajouter(self):
        if UtilisateurDialog(self.auth, self).exec() == QDialog.Accepted:
            self.recharger()

    def _reinitialiser(self):
        choix = self._selection()
        if not choix:
            return
        utilisateur_id, login = choix
        mdp, ok = QInputDialog.getText(
            self, "Réinitialiser", f"Nouveau mot de passe pour {login} :",
            QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            self.auth.reinitialiser_mot_de_passe(utilisateur_id, mdp)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        QMessageBox.information(self, "Mot de passe", "Mot de passe modifié.")

    def _supprimer(self):
        choix = self._selection()
        if not choix:
            return
        utilisateur_id, login = choix
        if QMessageBox.question(
                self, "Confirmation", f"Supprimer le compte {login} ?") != QMessageBox.Yes:
            return
        try:
            self.auth.supprimer_utilisateur(utilisateur_id)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Suppression impossible", str(e))
            return
        self.recharger()