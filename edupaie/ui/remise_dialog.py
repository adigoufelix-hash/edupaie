from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.paiement_dialog import fcfa

MOTIFS = ["Fratrie", "Bourse d'excellence", "Bourse sociale",
          "Exonération du personnel", "Geste commercial"]


class RemiseDialog(QDialog):
    def __init__(self, service, eleve, parent=None):
        super().__init__(parent)
        self.service, self.eleve = service, eleve
        self.setWindowTitle(f"Remise - {eleve.nom} {eleve.prenom}")
        self.setMinimumWidth(460)

        self.type = QComboBox()
        self.type.addItem("Montant (FCFA)", "montant")
        self.type.addItem("Pourcentage (%)", "pourcentage")
        self.valeur = QLineEdit()
        self.valeur.setPlaceholderText("Ex. : 20000 ou 25")
        self.motif = QComboBox()
        self.motif.setEditable(True)
        self.motif.addItems(MOTIFS)
        self.motif.setCurrentText("")
        self.motif.lineEdit().setPlaceholderText("Choisis ou écris le motif")
        self.apercu = QLabel()

        form = QFormLayout(self)
        form.addRow("Type de remise", self.type)
        form.addRow("Valeur", self.valeur)
        form.addRow("Motif", self.motif)
        form.addRow("", self.apercu)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

        self.type.currentIndexChanged.connect(self._maj_apercu)
        self.valeur.textChanged.connect(self._maj_apercu)
        self._maj_apercu()

    def _maj_apercu(self, *_):
        montant = self.service.montant_effectif(
            self.eleve.id, self.type.currentData(), self.valeur.text())
        self.apercu.setText(f"Montant de la remise : {fcfa(montant)}" if montant else "")

    def _valider(self):
        try:
            self.service.accorder(self.eleve.id, self.type.currentData(),
                                  self.valeur.text(), self.motif.currentText())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()