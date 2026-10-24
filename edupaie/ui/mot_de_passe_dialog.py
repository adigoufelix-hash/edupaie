from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
                               QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier


class MotDePasseDialog(QDialog):
    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Changer mon mot de passe")
        self.setMinimumWidth(380)
        self.ancien = self._champ()
        self.nouveau = self._champ()
        self.confirmation = self._champ()
        form = QFormLayout(self)
        form.addRow("Mot de passe actuel", self.ancien)
        form.addRow("Nouveau mot de passe", self.nouveau)
        form.addRow("Confirmation", self.confirmation)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    @staticmethod
    def _champ():
        champ = QLineEdit()
        champ.setEchoMode(QLineEdit.EchoMode.Password)
        return champ

    def _valider(self):
        if self.nouveau.text() != self.confirmation.text():
            QMessageBox.warning(self, "Données invalides",
                                "Les deux nouveaux mots de passe ne correspondent pas.")
            return
        try:
            self.auth.changer_mon_mot_de_passe(self.ancien.text(), self.nouveau.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        QMessageBox.information(self, "Mot de passe", "Mot de passe modifié.")
        self.accept()