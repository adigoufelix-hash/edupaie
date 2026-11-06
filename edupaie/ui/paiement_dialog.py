from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QMessageBox)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.recu_action import ouvrir_recu
MODES = [("Espèces", "especes"), ("Chèque", "cheque"),
         ("Virement", "virement"), ("Mobile money", "mobile_money")]

# Libellé et aide du champ « numéro », selon le mode de paiement
REFERENCES = {
    "mobile_money": ("N° de transaction", "Recopie-le depuis le SMS de confirmation"),
    "cheque": ("N° du chèque", "Facultatif"),
    "virement": ("N° du virement", "Facultatif"),
}


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
        self.etiquette_reference = QLabel()
        self.reference = QLineEdit()
        self.reference.setMaxLength(40)

        form = QFormLayout(self)
        form.addRow("Élève", QLabel(f"{eleve.nom} {eleve.prenom} ({eleve.classe})"))
        form.addRow("Total des frais", QLabel(fcfa(situation.total_du)))
        form.addRow("Déjà payé", QLabel(fcfa(situation.total_paye)))
        form.addRow("Solde restant", QLabel(fcfa(situation.solde)))
        form.addRow("Montant (FCFA)", self.montant)
        form.addRow("Date", self.date)
        form.addRow("Mode de paiement", self.mode)
        form.addRow(self.etiquette_reference, self.reference)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

        self.mode.currentIndexChanged.connect(self._afficher_reference)
        self._afficher_reference()

    def _afficher_reference(self, *_):
        """Le champ numéro n'existe pas pour les espèces ; son libellé suit le mode."""
        libelle, aide = REFERENCES.get(self.mode.currentData(), ("", ""))
        visible = bool(libelle)
        self.etiquette_reference.setText(libelle)
        self.reference.setPlaceholderText(aide)
        self.etiquette_reference.setVisible(visible)
        self.reference.setVisible(visible)
        self.adjustSize()

    def _valider(self):
        mode = self.mode.currentData()
        if mode == "mobile_money" and not self.reference.text().strip():
            reponse = QMessageBox.question(
                self, "Numéro de transaction absent",
                "Aucun numéro de transaction n'a été saisi.\n\n"
                "Recopie-le depuis le SMS de confirmation : il permet de retrouver ce "
                "paiement sur le relevé de l'opérateur sans erreur possible.\n\n"
                "Enregistrer quand même sans numéro ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reponse != QMessageBox.Yes:
                self.reference.setFocus()
                return
        try:
            self.paiement = self.service.enregistrer_paiement(
                self.eleve.id, self.montant.text(),
                self.date.date().toString("yyyy-MM-dd"), mode, self.reference.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Paiement refusé", str(e))
            return
        reponse = QMessageBox.question(
            self, "Paiement enregistré",
            f"Reçu n° {self.paiement.numero_recu}\n"
            f"Solde restant : {fcfa(self.paiement.solde_apres)}\n\n"
            "Ouvrir le reçu maintenant ?")
        if reponse == QMessageBox.StandardButton.Yes:
            ouvrir_recu(self, self.service, self.paiement.id)
        self.accept()