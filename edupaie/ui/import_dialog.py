from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.fichiers import apres_export
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table

FONDS = {"ok": None, "ignore": "#f3f4f6", "erreur": "#fee2e2"}


class ImportDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.analyse = None
        self.setWindowTitle("Importer des élèves depuis Excel")
        self.resize(1000, 620)

        aide = QLabel(
            "1. Télécharge le modèle Excel et remplis-le (ou utilise ton propre fichier "
            "avec au minimum les colonnes Nom, Prénom et Classe).<br>"
            "2. Choisis le fichier.<br>"
            "3. Vérifie l'aperçu : seules les lignes à importer seront enregistrées.")
        aide.setWordWrap(True)
        modele = QPushButton("Télécharger le modèle Excel")
        choisir = QPushButton("Choisir le fichier...")
        modele.clicked.connect(self._modele)
        choisir.clicked.connect(self._choisir)

        self.resume = QLabel("Aucun fichier choisi.")
        self.resume.setTextFormat(Qt.TextFormat.RichText)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Ligne", "Nom", "Prénom", "Classe", "Année", "Total dû", "Résultat"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        self.importer = QPushButton("Importer")
        self.importer.setEnabled(False)
        self.importer.clicked.connect(self._importer)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.reject)

        haut = QHBoxLayout()
        haut.addWidget(modele)
        haut.addWidget(choisir)
        haut.addStretch()
        bas = QHBoxLayout()
        bas.addStretch()
        bas.addWidget(self.importer)
        bas.addWidget(fermer)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(bas)

    def _modele(self):
        try:
            chemin = self.service.creer_modele("exports")
        except (ErreurMetier, OSError) as e:
            QMessageBox.warning(self, "Modèle impossible", str(e))
            return
        apres_export(self, chemin, "Modèle enregistré")

    def _choisir(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir le fichier Excel", "", "Classeur Excel (*.xlsx)")
        if not chemin:
            return
        try:
            self.analyse = self.service.analyser(chemin)
        except ErreurMetier as e:
            self.analyse = None
            self.importer.setEnabled(False)
            QMessageBox.warning(self, "Fichier refusé", str(e))
            return
        self._afficher()

    def _afficher(self):
        a = self.analyse
        self.table.setRowCount(len(a["lignes"]))
        for i, l in enumerate(a["lignes"]):
            total = fcfa(l["total"]) if isinstance(l["total"], int) else str(l["total"])
            resultat = "À importer" if l["statut"] == "ok" else l["message"]
            valeurs = [str(l["ligne"]), l["nom"], l["prenom"], l["classe"],
                       l["annee"], total, resultat]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if FONDS[l["statut"]]:
                    item.setBackground(QColor(FONDS[l["statut"]]))
                if l["statut"] == "erreur" and col == 6:
                    item.setForeground(QColor("#991b1b"))
                self.table.setItem(i, col, item)
        self.resume.setText(
            f"<b>{a['fichier']}</b> : <b>{a['nb_ok']}</b> élève(s) à importer - "
            f"{a['nb_ignores']} ignoré(s) - {a['nb_erreurs']} ligne(s) en erreur")
        self.importer.setText(f"Importer {a['nb_ok']} élève(s)")
        self.importer.setEnabled(a["nb_ok"] > 0)

    def _importer(self):
        try:
            nombre = self.service.importer(self.analyse)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Import impossible", str(e))
            return
        QMessageBox.information(self, "Import terminé", f"{nombre} élève(s) importé(s).")
        self.accept()