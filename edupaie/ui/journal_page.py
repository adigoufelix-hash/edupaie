from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.services.audit import LIBELLES, LIMITE, SENSIBLES
from edupaie.services.export_journal import exporter_journal
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.fichiers import apres_export
from edupaie.ui.style import preparer_table


class JournalPage(QWidget):
    def __init__(self, service, dossier_excel="exports"):
        super().__init__()
        self.service = service
        self.dossier_excel = dossier_excel
        self.lignes = []

        aujourdhui = QDate.currentDate()
        self.debut = QDateEdit(aujourdhui.addDays(-30))
        self.fin = QDateEdit(aujourdhui)
        for champ in (self.debut, self.fin):
            champ.setCalendarPopup(True)
            champ.setDisplayFormat("dd/MM/yyyy")
        self.categorie = QComboBox()
        self.categorie.addItem("Toutes les actions", None)
        for nom in service.categories():
            self.categorie.addItem(nom, nom)
        self.utilisateur = QComboBox()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("Rechercher dans le détail...")
        self._remplir_utilisateurs()

        self.resume = QLabel()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Date et heure", "Utilisateur", "Action", "Détail"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        actualiser = QPushButton("Actualiser")
        verifier = QPushButton("Vérifier l'intégrité")
        excel = QPushButton("Exporter en Excel")
        actualiser.clicked.connect(self._actualiser)
        verifier.clicked.connect(self._verifier)
        excel.clicked.connect(self._exporter)

        haut = QHBoxLayout()
        haut.addWidget(QLabel("Du"))
        haut.addWidget(self.debut)
        haut.addWidget(QLabel("au"))
        haut.addWidget(self.fin)
        haut.addWidget(self.categorie)
        haut.addWidget(self.utilisateur)
        haut.addWidget(self.recherche, 1)
        bas = QHBoxLayout()
        for bouton in (actualiser, verifier, excel):
            bas.addWidget(bouton)
        bas.addStretch()
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(bas)

        self.debut.dateChanged.connect(self.recharger)
        self.fin.dateChanged.connect(self.recharger)
        self.categorie.currentIndexChanged.connect(self.recharger)
        self.utilisateur.currentIndexChanged.connect(self.recharger)
        self.recherche.textChanged.connect(self.recharger)
        self.recharger()

    def _remplir_utilisateurs(self):
        courant = self.utilisateur.currentData()
        self.utilisateur.blockSignals(True)
        self.utilisateur.clear()
        self.utilisateur.addItem("Tous les utilisateurs", None)
        try:
            for nom in self.service.utilisateurs():
                self.utilisateur.addItem(nom, nom)
        except ErreurMetier:
            pass
        self.utilisateur.setCurrentIndex(max(self.utilisateur.findData(courant), 0))
        self.utilisateur.blockSignals(False)

    @staticmethod
    def _iso(champ) -> str:
        return champ.date().toString(Qt.DateFormat.ISODate)

    def _actualiser(self):
        self._remplir_utilisateurs()
        self.recharger()

    def recharger(self, *_):
        try:
            self.lignes = self.service.consulter(
                self._iso(self.debut), self._iso(self.fin), self.categorie.currentData(),
                self.utilisateur.currentData(), self.recherche.text())
        except ErreurMetier as e:
            self.lignes = []
            self.table.setRowCount(0)
            self.resume.setText(f"<span style='color:#991b1b'>{e}</span>")
            return
        texte = f"{len(self.lignes)} événement(s)"
        if len(self.lignes) >= LIMITE:
            texte += f" (affichage limité aux {LIMITE} plus récents : affine les filtres)"
        self.resume.setText(texte)
        self.table.setRowCount(len(self.lignes))
        for i, l in enumerate(self.lignes):
            quand = datetime.fromisoformat(l["date_heure"]).strftime("%d/%m/%Y %H:%M")
            valeurs = [quand, l["utilisateur"] or "-",
                       LIBELLES.get(l["action"], l["action"]), l["detail"]]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if l["action"] in SENSIBLES:
                    item.setForeground(QColor("#991b1b"))
                self.table.setItem(i, col, item)

    def _verifier(self):
        try:
            resultat = self.service.verifier()
        except ErreurMetier as e:
            QMessageBox.warning(self, "Vérification impossible", str(e))
            return
        if resultat["ok"]:
            QMessageBox.information(
                self, "Journal intact",
                f"{resultat['nb']} événement(s) vérifié(s) : aucune modification détectée.")
        else:
            QMessageBox.critical(self, "Journal altéré", resultat["message"])

    def _exporter(self):
        if not self.lignes:
            QMessageBox.information(self, "Export", "Aucun événement à exporter.")
            return
        try:
            chemin = exporter_journal(self.lignes, self.dossier_excel)
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        apres_export(self, chemin)