from datetime import date

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.paiement_dialog import fcfa

CLASSES = ["6e A", "6e B", "5e A", "5e B", "4e A", "4e B", "3e A", "3e B",
           "2nde", "1ère", "Tle"]


def annees_scolaires(n=5):
    y = date.today().year
    return [f"{a}-{a + 1}" for a in range(y - 2, y + n - 2)]


def annee_courante() -> str:
    t = date.today()
    debut = t.year if t.month >= 8 else t.year - 1
    return f"{debut}-{debut + 1}"


class EleveDialog(QDialog):
    def __init__(self, service, eleve=None, parent=None, frais=None):
        super().__init__(parent)
        self.service, self.eleve, self.frais = service, eleve, frais
        self._total_manuel = False
        self.setWindowTitle("Modifier l'élève" if eleve else "Nouvel élève")
        self.setMinimumWidth(460)

        self.nom, self.prenom = QLineEdit(), QLineEdit()
        classes = (frais.classes() if frais else []) or CLASSES
        self.classe = QComboBox()
        self.classe.addItems(classes)
        self.classe.setEditable(True)
        self.annee = QComboBox()
        self.annee.addItems(annees_scolaires())
        self.annee.setEditable(True)
        self.annee.setCurrentText(annee_courante())
        self.info_frais = QLabel()
        self.info_frais.setWordWrap(True)
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
                               ("Frais de la classe", self.info_frais),
                               ("Total des frais (FCFA)", self.total)):
            form.addRow(libelle, champ)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

        self.total.textEdited.connect(self._marquer_manuel)
        self.classe.currentTextChanged.connect(self._proposer_total)
        self.annee.currentTextChanged.connect(self._proposer_total)
        self._proposer_total()

    def _marquer_manuel(self, *_):
        self._total_manuel = True

    def _proposer_total(self, *_):
        """Affiche les frais de la classe ; remplit le total pour un nouvel élève."""
        if self.frais is None:
            return
        classe = self.classe.currentText().strip()
        annee = self.annee.currentText().strip()
        lignes = self.frais.detail(classe, annee) if classe and annee else []
        if not lignes:
            self.info_frais.setText(
                "Aucun frais défini pour cette classe : saisis le total à la main.")
            return
        total = sum(l["montant"] for l in lignes)
        detail = " + ".join(f"{l['libelle']} {fcfa(l['montant'])}" for l in lignes)
        self.info_frais.setText(f"{detail} = {fcfa(total)}")
        if self.eleve is None and not self._total_manuel:
            self.total.setText(str(total))

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