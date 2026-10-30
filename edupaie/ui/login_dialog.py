from PySide6.QtWidgets import (QDialog, QFormLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.recuperation_dialogs import (ChangementObligatoireDialog,
                                             CodesSecoursDialog, RecuperationDialog)


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

        self.oublie = QLabel("<a href='#'>Mot de passe oublié ?</a>")
        self.oublie.linkActivated.connect(self._oublie)
        self.oublie.setVisible(not self.premier_lancement)

        self.bouton = QPushButton(
            "Créer le compte" if self.premier_lancement else "Se connecter"
        )
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
        layout.addWidget(self.oublie)
        layout.addWidget(self.bouton)

    def _valider(self):
        self.erreur.setText("")
        if self.premier_lancement:
            self._creer_admin()
        else:
            self._connecter()

    def _nouveau_mot_de_passe(self) -> bool:
        return ChangementObligatoireDialog(self.auth, self).exec() == QDialog.Accepted

    def _connecter(self):
        try:
            utilisateur = self.auth.authentifier(self.login.text(), self.mdp.text())
        except ErreurMetier as e:  # trop de tentatives
            self.erreur.setText(str(e))
            return
        if utilisateur:
            if utilisateur.get("doit_changer_mdp") and not self._nouveau_mot_de_passe():
                self.auth.deconnecter()
                self.mdp.clear()
                self.erreur.setText(
                    "Tu dois choisir un nouveau mot de passe pour te connecter.")
                return
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
        except (ErreurMetier, ValueError) as e:
            self.erreur.setText(str(e))
            return
        self.auth.authentifier(self.login.text(), self.mdp.text())
        try:
            codes = self.auth.generer_codes_secours(self.mdp.text())
        except ErreurMetier:
            codes = []
        if codes:  # à noter tout de suite : ils ne seront plus affichés
            CodesSecoursDialog(codes, self.nom.text().strip(), self).exec()
        self.accept()

    def _oublie(self, *_):
        dialogue = RecuperationDialog(self.auth, self.login.text(), self)
        if dialogue.exec() == QDialog.Accepted:
            self.login.setText(dialogue.login_saisi)
            self.mdp.clear()
            self.mdp.setFocus()
            self.erreur.setText("")
            self.essais = 0