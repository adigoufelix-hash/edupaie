import sqlite3

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)


class LoginDialog(QDialog):
    MAX_ESSAIS = 5

    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.premier_lancement = auth.aucun_utilisateur()
        self.essais = 0

        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowTitle(
            "EduPaie : création du compte administrateur"
            if self.premier_lancement else "EduPaie : connexion"
        )

        titre = QLabel(
            "Premier lancement : créez le compte administrateur."
            if self.premier_lancement else "Connectez-vous pour continuer."
        )
        titre.setWordWrap(True)

        self.nom = QLineEdit()
        self.login = QLineEdit()
        self.mdp = QLineEdit()
        self.mdp.setEchoMode(QLineEdit.EchoMode.Password)
        self.mdp2 = QLineEdit()
        self.mdp2.setEchoMode(QLineEdit.EchoMode.Password)

        self.erreur = QLabel("")
        self.erreur.setWordWrap(True)
        self.erreur.setStyleSheet("color: #c0392b;")

        self.bouton = QPushButton("Créer le compte" if self.premier_lancement else "Se connecter")
        self.bouton.setDefault(True)
        self.bouton.clicked.connect(self._valider)

        form = QFormLayout()
        if self.premier_lancement:
            form.addRow("Nom complet", self.nom)
        form.addRow("Identifiant", self.login)
        form.addRow("Mot de passe", self.mdp)
        if self.premier_lancement:
            form.addRow("Confirmation", self.mdp2)

        layout = QVBoxLayout(self)
        layout.addWidget(titre)
        layout.addLayout(form)
        layout.addWidget(self.erreur)
        layout.addWidget(self.bouton)

    def _valider(self):
        self.erreur.setText("")
        if self.premier_lancement:
            self._creer_admin()
        else:
            self._connecter()

    def _connecter(self):
        if self.auth.authentifier(self.login.text(), self.mdp.text()):
            self.accept()
            return
        self.essais += 1
        if self.essais >= self.MAX_ESSAIS:
            self.reject()
            return
        self.erreur.setText("Identifiants incorrects.")
        self.mdp.clear()
        self.mdp.setFocus()

    def _creer_admin(self):
        if not self.nom.text().strip() or not self.login.text().strip():
            self.erreur.setText("Le nom complet et l'identifiant sont obligatoires.")
            return
        if self.mdp.text() != self.mdp2.text():
            self.erreur.setText("Les deux mots de passe ne correspondent pas.")
            return
        try:
            self.auth.creer_utilisateur(
                self.login.text(), self.nom.text(), self.mdp.text(), "admin"
            )
        except ValueError as e:
            self.erreur.setText(str(e))
            return
        except sqlite3.IntegrityError:
            self.erreur.setText("Cet identifiant existe déjà.")
            return
        self.auth.authentifier(self.login.text(), self.mdp.text())
        self.accept()