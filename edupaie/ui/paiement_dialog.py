from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier

MODES = [("Espèces", "especes"), ("Chèque", "cheque"),
         ("Virement", "virement"), ("Mobile money", "mobile_money")]


def fcfa(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ") + " FCFA"


class PaiementDialog(QDialog):
    def __init__(self, service, eleve, parent=None):
        super().__init__(parent)
        self.service, self.eleve, self.paiement = service, eleve, None
        self.setWindowTitle("Enregistrer un paiement")
        situation = service.situation(eleve.id)

        self.montant = QLineEdit()
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.date.setMaximumDate(QDate.currentDate())
        self.mode = QComboBox()
        for libelle, valeur in MODES:
            self.mode.addItem(libelle, valeur)

        form = QFormLayout(self)
        form.addRow("Élève", QLabel(f"{eleve.nom} {eleve.prenom} ({eleve.classe})"))
        form.addRow("Total des frais", QLabel(fcfa(situation.total_du)))
        form.addRow("Déjà payé", QLabel(fcfa(situation.total_paye)))
        form.addRow("Solde restant", QLabel(fcfa(situation.solde)))
        form.addRow("Montant (FCFA)", self.montant)
        form.addRow("Date", self.date)
        form.addRow("Mode de paiement", self.mode)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        try:
            self.paiement = self.service.enregistrer_paiement(
                self.eleve.id, self.montant.text(),
                self.date.date().toString("yyyy-MM-dd"), self.mode.currentData())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Paiement refusé", str(e))
            return
        QMessageBox.information(
            self, "Paiement enregistré",
            f"Reçu n° {self.paiement.numero_recu}\n"
            f"Solde restant : {fcfa(self.paiement.solde_apres)}")
        self.accept()