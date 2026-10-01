from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
                               QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier


class EleveDialog(QDialog):
    def __init__(self, service, eleve=None, parent=None):
        super().__init__(parent)
        self.service, self.eleve = service, eleve
        self.setWindowTitle("Modifier l'élève" if eleve else "Nouvel élève")
        self.nom, self.prenom = QLineEdit(), QLineEdit()
        self.classe, self.annee = QLineEdit(), QLineEdit("2026-2027")
        self.total = QLineEdit()
        if eleve:
            self.nom.setText(eleve.nom)
            self.prenom.setText(eleve.prenom)
            self.classe.setText(eleve.classe)
            self.annee.setText(eleve.annee_scolaire)
            self.total.setText(str(eleve.total_du))
        form = QFormLayout(self)
        for libelle, champ in (("Nom", self.nom), ("Prénom", self.prenom),
                               ("Classe", self.classe),
                               ("Année scolaire", self.annee),
                               ("Total des frais (FCFA)", self.total)):
            form.addRow(libelle, champ)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        try:
            self.service.enregistrer(
                self.eleve.id if self.eleve else None, self.nom.text(),
                self.prenom.text(), self.classe.text(), self.annee.text(),
                self.total.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()