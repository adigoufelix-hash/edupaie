from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.style import preparer_table


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


class LigneEcheanceDialog(QDialog):
    def __init__(self, service, classe, annee, ligne=None, parent=None):
        super().__init__(parent)
        self.service, self.classe, self.annee, self.ligne = service, classe, annee, ligne
        self.setWindowTitle("Modifier la tranche" if ligne else "Nouvelle tranche")
        self.setMinimumWidth(400)
        self.libelle = QLineEdit()
        self.libelle.setPlaceholderText("Ex. : 1re tranche, Trimestre 1")
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.pourcentage = QLineEdit()
        self.pourcentage.setPlaceholderText("Ex. : 40")
        if ligne:
            self.libelle.setText(ligne["libelle"])
            self.date.setDate(QDate.fromString(ligne["date_limite"], Qt.DateFormat.ISODate))
            self.pourcentage.setText(str(ligne["pourcentage"]))
        form = QFormLayout(self)
        form.addRow("Classe", QLabel(f"{classe} ({annee})"))
        form.addRow("Nom de la tranche", self.libelle)
        form.addRow("Date limite", self.date)
        form.addRow("Part du total (%)", self.pourcentage)
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.accepted.connect(self._valider)
        boutons.rejected.connect(self.reject)
        form.addRow(boutons)

    def _valider(self):
        iso = self.date.date().toString(Qt.DateFormat.ISODate)
        try:
            if self.ligne:
                self.service.modifier_ligne(self.ligne["id"], self.libelle.text(),
                                            iso, self.pourcentage.text())
            else:
                self.service.ajouter_ligne(self.classe, self.annee, self.libelle.text(),
                                           iso, self.pourcentage.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        self.accept()


class EcheancierDialog(QDialog):
    def __init__(self, service, classe, annee, parent=None):
        super().__init__(parent)
        self.service, self.classe, self.annee = service, classe, annee
        self.setWindowTitle(f"Échéancier - {classe} ({annee})")
        self.resize(800, 440)

        aide = QLabel(
            "Chaque tranche est une part du total de l'élève (remises déduites). "
            "Exemple : 40 % au 15/10 = un élève qui doit 100 000 FCFA doit avoir "
            "payé 40 000 FCFA à cette date. Le total des tranches doit faire 100 %.")
        aide.setWordWrap(True)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tranche", "Date limite", "Part du total"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)
        self.total = QLabel()
        self.total.setTextFormat(Qt.TextFormat.RichText)

        ajouter = QPushButton("Ajouter une tranche")
        modifier = QPushButton("Modifier")
        supprimer = QPushButton("Supprimer")
        supprimer.setObjectName("danger")
        copier = QPushButton("Copier vers une autre classe")
        fermer = QPushButton("Fermer")
        ajouter.clicked.connect(self._ajouter)
        modifier.clicked.connect(self._modifier)
        supprimer.clicked.connect(self._supprimer)
        copier.clicked.connect(self._copier)
        fermer.clicked.connect(self.accept)
        boutons = QHBoxLayout()
        for b in (ajouter, modifier, supprimer, copier):
            boutons.addWidget(b)
        boutons.addStretch()
        boutons.addWidget(fermer)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(aide)
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.total)
        mise_en_page.addLayout(boutons)
        self.recharger()

    def recharger(self):
        lignes = self.service.lister(self.classe, self.annee)
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            self.table.setItem(i, 0, QTableWidgetItem(l["libelle"]))
            self.table.setItem(i, 1, QTableWidgetItem(_date_fr(l["date_limite"])))
            self.table.setItem(i, 2, QTableWidgetItem(f"{l['pourcentage']} %"))
            self.table.item(i, 0).setData(Qt.UserRole, {
                "id": l["id"], "libelle": l["libelle"],
                "date_limite": l["date_limite"], "pourcentage": l["pourcentage"]})
        total = self.service.total_pourcentage(self.classe, self.annee)
        if total == 100:
            self.total.setText("<b style='color:#166534'>Total : 100 % ✔</b>")
        elif total == 0:
            self.total.setText("Aucune tranche : les élèves de cette classe ne sont "
                               "pas suivis dans l'écran Impayés.")
        else:
            self.total.setText(f"<b style='color:#9a3412'>Total : {total} % - "
                               f"il manque {100 - total} %</b>")

    def _selection(self):
        i = self.table.currentRow()
        if i < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord une tranche.")
            return None
        return self.table.item(i, 0).data(Qt.UserRole)

    def _ajouter(self):
        if LigneEcheanceDialog(self.service, self.classe, self.annee,
                               parent=self).exec() == QDialog.Accepted:
            self.recharger()

    def _modifier(self):
        ligne = self._selection()
        if ligne and LigneEcheanceDialog(self.service, self.classe, self.annee,
                                         ligne, self).exec() == QDialog.Accepted:
            self.recharger()

    def _supprimer(self):
        ligne = self._selection()
        if not ligne:
            return
        if QMessageBox.question(self, "Confirmation",
                                f"Supprimer la tranche « {ligne['libelle']} » ?") != QMessageBox.Yes:
            return
        try:
            self.service.supprimer_ligne(ligne["id"])
        except ErreurMetier as e:
            QMessageBox.warning(self, "Suppression impossible", str(e))
            return
        self.recharger()

    def _copier(self):
        autres = [c for c in self.service.classes() if c != self.classe]
        cible, ok = QInputDialog.getItem(
            self, "Copier l'échéancier",
            f"Copier les tranches de {self.classe} vers la classe :", autres, 0, True)
        if not ok or not cible.strip():
            return
        try:
            n = self.service.copier(self.classe, self.annee, cible)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Copie impossible", str(e))
            return
        QMessageBox.information(self, "Copie", f"{n} tranche(s) copiée(s) vers {cible.strip()}.")