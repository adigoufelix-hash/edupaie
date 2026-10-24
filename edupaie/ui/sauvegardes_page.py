from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.style import preparer_table

MOTIFS = {"auto": "Automatique", "manuelle": "Manuelle",
          "avant-restauration": "Avant une restauration"}


def _taille(octets: int) -> str:
    if octets < 1024 * 1024:
        return f"{octets / 1024:.0f} Ko"
    return f"{octets / 1024 / 1024:.1f} Mo"


class SauvegardesPage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service

        info = QLabel(
            "Une copie automatique est faite à l'ouverture et à la fermeture "
            f"(les {service.garder} dernières sont conservées).<br>"
            f"Dossier : {service.dossier}<br><b>Conseil :</b> copie régulièrement "
            "une sauvegarde sur une clé USB ou un disque externe.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Date", "Type", "Taille"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        maintenant = QPushButton("Sauvegarder maintenant")
        ailleurs = QPushButton("Copier vers une clé USB / un dossier…")
        restaurer = QPushButton("Restaurer la sélection")
        restaurer.setObjectName("danger")
        maintenant.clicked.connect(self._sauvegarder)
        ailleurs.clicked.connect(self._copier_ailleurs)
        restaurer.clicked.connect(self._restaurer)

        bas = QHBoxLayout()
        for b in (maintenant, ailleurs, restaurer):
            bas.addWidget(b)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(info)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(bas)
        self.recharger()

    def recharger(self):
        sauvegardes = self.service.lister()
        self.table.setRowCount(len(sauvegardes))
        for i, s in enumerate(sauvegardes):
            self.table.setItem(i, 0, QTableWidgetItem(s["date"].strftime("%d/%m/%Y %H:%M")))
            self.table.setItem(i, 1, QTableWidgetItem(MOTIFS.get(s["motif"], s["motif"])))
            self.table.setItem(i, 2, QTableWidgetItem(_taille(s["taille"])))
            self.table.item(i, 0).setData(Qt.UserRole, str(s["chemin"]))

    def _sauvegarder(self):
        try:
            self.service.sauvegarder("manuelle")
        except ErreurMetier as e:
            QMessageBox.warning(self, "Sauvegarde impossible", str(e))
            return
        self.recharger()
        QMessageBox.information(self, "Sauvegarde", "Sauvegarde effectuée.")

    def _copier_ailleurs(self):
        dossier = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier (clé USB, disque externe...)")
        if not dossier:
            return
        try:
            chemin = self.service.sauvegarder("manuelle", dossier=dossier)
        except (ErreurMetier, OSError) as e:
            QMessageBox.warning(self, "Copie impossible", str(e))
            return
        QMessageBox.information(self, "Sauvegarde", f"Copie enregistrée :\n{chemin}")

    def _restaurer(self):
        i = self.table.currentRow()
        if i < 0:
            QMessageBox.information(self, "Sélection",
                                    "Sélectionne d'abord une sauvegarde.")
            return
        chemin = self.table.item(i, 0).data(Qt.UserRole)
        date = self.table.item(i, 0).text()
        reponse = QMessageBox.question(
            self, "Restaurer",
            f"Remplacer toutes les données actuelles par celles du {date} ?\n\n"
            "Une copie des données actuelles est faite avant. "
            "L'application se fermera ensuite.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reponse != QMessageBox.Yes:
            return
        try:
            self.service.restaurer(chemin)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Restauration impossible", str(e))
            return
        QMessageBox.information(
            self, "Restauration terminée",
            "Les données sont restaurées. EduPaie va se fermer : relance-le "
            "pour travailler sur les données restaurées.")
        self.window().close()