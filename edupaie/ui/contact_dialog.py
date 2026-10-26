from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                               QMessageBox)

from edupaie.services.paiement_service import ErreurMetier


class ContactDialog(QDialog):
    def __init__(self, service, eleve_id, nom_eleve, parent=None):
        super().__init__(parent)
        self.service, self.eleve_id = service, eleve_id
        self.setWindowTitle(f"Contact du parent - {nom_eleve}")
        self.setMinimumWidth(460)
        contact = service.contact(eleve_id)
        self.tuteur = QLineEdit(contact["tuteur"] or "" if contact else "")
        self.tuteur.setPlaceholderText("Nom du parent ou tuteur")
        self.telephone = QLineEdit(contact["telephone"] or "" if contact else "")
        self.telephone.setPlaceholderText("Ex. : 90 12 34 56 ou +233 24 123 4567")
        form = QFormLayout(self)
        form.addRow("Parent / tuteur", self.tuteur)
        form.addRow("Téléphone (WhatsApp)", self.telephone)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        try:
            self.service.enregistrer_contact(
                self.eleve_id, self.tuteur.text(), self.telephone.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()