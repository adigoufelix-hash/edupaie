from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.permissions import ROLES
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.recuperation_dialogs import CodesSecoursDialog
from edupaie.ui.style import preparer_table


class UtilisateurDialog(QDialog):
    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Nouvel utilisateur")
        self.setMinimumWidth(440)
        self.login = QLineEdit()
        self.nom = QLineEdit()
        self.role = QComboBox()
        self.role.addItems(ROLES)
        self.mdp = QLineEdit()
        self.mdp.setEchoMode(QLineEdit.EchoMode.Password)
        self.mdp2 = QLineEdit()
        self.mdp2.setEchoMode(QLineEdit.EchoMode.Password)
        aide = QLabel("Ce mot de passe est temporaire : l'utilisateur devra en choisir "
                      "un nouveau à sa première connexion.")
        aide.setWordWrap(True)
        form = QFormLayout(self)
        form.addRow("Identifiant", self.login)
        form.addRow("Nom complet", self.nom)
        form.addRow("Rôle", self.role)
        form.addRow("Mot de passe temporaire", self.mdp)
        form.addRow("Confirmation", self.mdp2)
        form.addRow(aide)
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

        self.alerte = QLabel(
            "⚠ Il n'y a qu'un seul compte administrateur. Si son mot de passe et ses codes "
            "de secours sont perdus, plus personne ne pourra gérer les comptes : crée un "
            "second compte administrateur.")
        self.alerte.setWordWrap(True)
        self.alerte.setStyleSheet(
            "background: #ffedd5; color: #9a3412; border-radius: 8px; padding: 10px;")
        self.codes = QLabel()
        self.codes.setWordWrap(True)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Identifiant", "Nom complet", "Rôle", "Mot de passe"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        ajouter = QPushButton("Ajouter un utilisateur")
        reinit = QPushButton("Réinitialiser le mot de passe")
        supprimer = QPushButton("Supprimer")
        supprimer.setObjectName("danger")
        mes_codes = QPushButton("Mes codes de secours")
        ajouter.clicked.connect(self._ajouter)
        reinit.clicked.connect(self._reinitialiser)
        supprimer.clicked.connect(self._supprimer)
        mes_codes.clicked.connect(self._mes_codes)

        bas = QHBoxLayout()
        for bouton in (ajouter, reinit, supprimer, mes_codes):
            bas.addWidget(bouton)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(self.alerte)
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.codes)
        mise_en_page.addLayout(bas)
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()

    def recharger(self):
        try:
            lignes = self.auth.lister_utilisateurs()
        except ErreurMetier as e:
            QMessageBox.warning(self, "Accès refusé", str(e))
            return
        self.table.setRowCount(len(lignes))
        for i, ligne in enumerate(lignes):
            valeurs = (ligne["login"], ligne["nom_complet"], ligne["role"],
                       "Temporaire" if ligne["doit_changer_mdp"] else "Personnel")
            for col, valeur in enumerate(valeurs):
                self.table.setItem(i, col, QTableWidgetItem(str(valeur)))
            self.table.item(i, 0).setData(Qt.UserRole, ligne["id"])
        self.alerte.setVisible(self.auth.nombre_admins() < 2)
        restants = self.auth.codes_secours_restants()
        if restants:
            self.codes.setText(f"Mes codes de secours restants : {restants}")
        else:
            self.codes.setText(
                "<span style='color:#991b1b'>Tu n'as aucun code de secours : génère-en "
                "pour pouvoir récupérer ton mot de passe.</span>")

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
            self, "Réinitialiser", f"Mot de passe temporaire pour {login} :",
            QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            self.auth.reinitialiser_mot_de_passe(utilisateur_id, mdp)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        QMessageBox.information(
            self, "Mot de passe",
            f"Mot de passe temporaire enregistré. {login} devra en choisir un nouveau "
            "à sa prochaine connexion.")
        self.recharger()

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

    def _mes_codes(self):
        mdp, ok = QInputDialog.getText(
            self, "Codes de secours",
            "Pour générer de nouveaux codes (les anciens seront invalidés), entre ton "
            "mot de passe actuel :", QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            codes = self.auth.generer_codes_secours(mdp)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Codes impossibles", str(e))
            return
        CodesSecoursDialog(codes, self.auth.utilisateur["nom_complet"], self).exec()
        self.recharger()