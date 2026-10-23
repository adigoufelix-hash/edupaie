from datetime import date

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier

CLASSES = ["6e A", "6e B", "5e A", "5e B", "4e A", "4e B", "3e A", "3e B",
           "2nde", "1ère", "Tle"]


def annees_scolaires(n=5):
    y = date.today().year
    return [f"{a}-{a + 1}" for a in range(y - 2, y + n - 2)]


class EleveDialog(QDialog):
    def __init__(self, service, eleve=None, parent=None):
        super().__init__(parent)
        self.service, self.eleve = service, eleve
        self.setWindowTitle("Modifier l'élève" if eleve else "Nouvel élève")

        self.nom, self.prenom = QLineEdit(), QLineEdit()
        self.classe = QComboBox()
        self.classe.addItems(CLASSES)
        self.classe.setEditable(True)
        self.annee = QComboBox()
        self.annee.addItems(annees_scolaires())
        self.annee.setEditable(True)
        self.annee.setCurrentText("2026-2027")
        self.total = QLineEdit()

        if eleve:
            self.nom.setText(eleve.nom)
            self.prenom.setText(eleve.prenom)
            self.classe.setCurrentText(eleve.classe)
            self.annee.setCurrentText(eleve.annee_scolaire)
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
                self.prenom.text(), self.classe.currentText().strip(),
                self.annee.currentText().strip(), self.total.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()