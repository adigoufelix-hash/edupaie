from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.eleve_dialog import CLASSES, annee_courante, annees_scolaires
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table


class LigneFraisDialog(QDialog):
    def __init__(self, service, classe, annee, ligne=None, parent=None):
        super().__init__(parent)
        self.service, self.classe, self.annee, self.ligne = service, classe, annee, ligne
        self.setWindowTitle(
            "Modifier la ligne de frais" if ligne else "Nouvelle ligne de frais")
        self.setMinimumWidth(400)
        self.libelle = QLineEdit()
        self.libelle.setPlaceholderText("Ex. : Inscription, Scolarité, Examen, Uniforme")
        self.montant = QLineEdit()
        self.montant.setPlaceholderText("Montant en FCFA")
        if ligne:
            self.libelle.setText(ligne["libelle"])
            self.montant.setText(str(ligne["montant"]))
        form = QFormLayout(self)
        form.addRow("Classe", QLabel(f"{classe} ({annee})"))
        form.addRow("Libellé", self.libelle)
        form.addRow("Montant (FCFA)", self.montant)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        try:
            if self.ligne:
                self.service.modifier_ligne(
                    self.ligne["id"], self.libelle.text(), self.montant.text())
            else:
                self.service.ajouter_ligne(
                    self.classe, self.annee, self.libelle.text(), self.montant.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()


class FraisPage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service

        self.classe = QComboBox()
        self.classe.setEditable(True)
        self.annee = QComboBox()
        self.annee.setEditable(True)
        self.annee.addItems(annees_scolaires())
        self.annee.setCurrentText(annee_courante())
        self._remplir_classes()

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Libellé", "Montant"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        self.total = QLabel()
        self.total.setTextFormat(Qt.TextFormat.RichText)

        ajouter = QPushButton("Ajouter une ligne")
        modifier = QPushButton("Modifier")
        supprimer = QPushButton("Supprimer")
        supprimer.setObjectName("danger")
        copier = QPushButton("Copier vers une autre classe")
        ajouter.clicked.connect(self._ajouter)
        modifier.clicked.connect(self._modifier)
        supprimer.clicked.connect(self._supprimer)
        copier.clicked.connect(self._copier)

        haut = QHBoxLayout()
        haut.addWidget(QLabel("Classe"))
        haut.addWidget(self.classe, 1)
        haut.addWidget(QLabel("Année scolaire"))
        haut.addWidget(self.annee, 1)
        bas = QHBoxLayout()
        for b in (ajouter, modifier, supprimer, copier):
            bas.addWidget(b)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.total)
        mise_en_page.addLayout(bas)

        self.classe.currentTextChanged.connect(self.recharger)
        self.annee.currentTextChanged.connect(self.recharger)
        self.recharger()

    def _classe(self) -> str:
        return self.classe.currentText().strip()

    def _annee(self) -> str:
        return self.annee.currentText().strip()

    def _remplir_classes(self, garder: str | None = None):
        courante = garder or self.classe.currentText()
        self.classe.blockSignals(True)
        self.classe.clear()
        self.classe.addItems(self.service.classes() or CLASSES)
        self.classe.setCurrentText(courante or self.classe.itemText(0))
        self.classe.blockSignals(False)

    def recharger(self, *_):
        lignes = self.service.detail(self._classe(), self._annee())
        self.table.setRowCount(len(lignes))
        for i, ligne in enumerate(lignes):
            self.table.setItem(i, 0, QTableWidgetItem(ligne["libelle"]))
            self.table.setItem(i, 1, QTableWidgetItem(fcfa(ligne["montant"])))
            self.table.item(i, 0).setData(Qt.UserRole, {
                "id": ligne["id"], "libelle": ligne["libelle"],
                "montant": ligne["montant"]})
        if lignes:
            total = sum(l["montant"] for l in lignes)
            self.total.setText(
                f"<b>Total des frais pour {self._classe()} "
                f"({self._annee()}) : {fcfa(total)}</b>")
        else:
            self.total.setText(
                "Aucun frais défini : ajoute les lignes (inscription, scolarité...).")

    def _ligne_selectionnee(self):
        i = self.table.currentRow()
        if i < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord une ligne.")
            return None
        return self.table.item(i, 0).data(Qt.UserRole)

    def _ajouter(self):
        if not self._classe() or not self._annee():
            QMessageBox.information(self, "Classe", "Indique d'abord la classe et l'année.")
            return
        if LigneFraisDialog(self.service, self._classe(), self._annee(),
                            parent=self).exec() == QDialog.Accepted:
            self._remplir_classes(garder=self._classe())
            self.recharger()

    def _modifier(self):
        ligne = self._ligne_selectionnee()
        if ligne and LigneFraisDialog(self.service, self._classe(), self._annee(),
                                      ligne, self).exec() == QDialog.Accepted:
            self.recharger()

    def _supprimer(self):
        ligne = self._ligne_selectionnee()
        if not ligne:
            return
        if QMessageBox.question(
                self, "Confirmation",
                f"Supprimer la ligne « {ligne['libelle']} » ?") != QMessageBox.Yes:
            return
        try:
            self.service.supprimer_ligne(ligne["id"])
        except ErreurMetier as e:
            QMessageBox.warning(self, "Suppression impossible", str(e))
            return
        self.recharger()

    def _copier(self):
        classe = self._classe()
        autres = [c for c in (self.service.classes() or CLASSES) if c != classe]
        cible, ok = QInputDialog.getItem(
            self, "Copier les frais",
            f"Copier les frais de {classe} vers la classe :", autres, 0, True)
        if not ok or not cible.strip():
            return
        try:
            n = self.service.copier(classe, self._annee(), cible)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Copie impossible", str(e))
            return
        QMessageBox.information(self, "Copie",
                                f"{n} ligne(s) copiée(s) vers {cible.strip()}.")
        self._remplir_classes(garder=classe)