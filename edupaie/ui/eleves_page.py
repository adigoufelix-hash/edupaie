from PySide6.QtGui import QColor, Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout,
                               QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.eleve_dialog import EleveDialog
from edupaie.ui.paiement_dialog import PaiementDialog


def fcfa(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ") + " FCFA"


class ElevesPage(QWidget):
    def __init__(self, service, paiement_service):
        super().__init__()
        self.service = service
        self.paiement_service = paiement_service
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("Rechercher par nom ou prénom...")
        self.filtre = QComboBox()
        self.filtre_statut = QComboBox()
        self.filtre_statut.addItem("Tous les statuts", None)
        for statut in ("Soldé", "Partiellement payé", "Non payé"):
            self.filtre_statut.addItem(statut, statut)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Nom", "Prénom", "Classe", "Année", "Total dû", "Payé", "Solde", "Statut"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        ajouter = QPushButton("Ajouter")
        modifier = QPushButton("Modifier")
        supprimer = QPushButton("Supprimer")
        haut, bas = QHBoxLayout(), QHBoxLayout()
        haut.addWidget(self.recherche, 1)
        haut.addWidget(self.filtre)
        haut.addWidget(self.filtre_statut)
        for b in (ajouter, modifier, supprimer):
            bas.addWidget(b)
        payer = QPushButton("Enregistrer un paiement")
        bas.addWidget(payer)
        payer.clicked.connect(self._payer)
        bas.addStretch()  
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(bas)

        self.recherche.textChanged.connect(self.recharger)
        self.filtre.currentIndexChanged.connect(self.recharger)
        self.filtre_statut.currentIndexChanged.connect(self.recharger)
        ajouter.clicked.connect(self._ajouter)
        modifier.clicked.connect(self._modifier)
        supprimer.clicked.connect(self._supprimer)
        self._remplir_classes()
        self.recharger()

    def _remplir_classes(self):
        self.filtre.blockSignals(True)
        courante = self.filtre.currentData()
        self.filtre.clear()
        self.filtre.addItem("Toutes les classes", None)
        for c in self.service.classes():
            self.filtre.addItem(c, c)
        index = self.filtre.findData(courante)
        self.filtre.setCurrentIndex(max(index, 0))
        self.filtre.blockSignals(False)

    def recharger(self):
        situations = self.paiement_service.situations(
            self.recherche.text().strip(), self.filtre.currentData(),
            self.filtre_statut.currentData())
        couleurs = {"Soldé": "#2e7d32", "Partiellement payé": "#ef6c00",
                    "Non payé": "#c62828"}
        self.table.setRowCount(len(situations))
        for ligne, (e, s) in enumerate(situations):
            valeurs = [e.nom, e.prenom, e.classe, e.annee_scolaire,
                       fcfa(s.total_du), fcfa(s.total_paye), fcfa(s.solde), s.statut]
            for col, texte in enumerate(valeurs):
                self.table.setItem(ligne, col, QTableWidgetItem(texte))
            self.table.item(ligne, 0).setData(Qt.UserRole, e.id)
            self.table.item(ligne, 7).setForeground(QColor(couleurs[s.statut]))

    def _eleve_selectionne(self):
        ligne = self.table.currentRow()
        if ligne < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord un élève.")
            return None
        eleve_id = self.table.item(ligne, 0).data(Qt.UserRole)
        return next(e for e in self.service.lister() if e.id == eleve_id)

    def _ajouter(self):
        if EleveDialog(self.service, parent=self).exec():
            self._remplir_classes()
            self.recharger()

    def _modifier(self):
        eleve = self._eleve_selectionne()
        if eleve and EleveDialog(self.service, eleve, self).exec():
            self._remplir_classes()
            self.recharger()

    def _supprimer(self):
        eleve = self._eleve_selectionne()
        if not eleve:
            return
        reponse = QMessageBox.question(
            self, "Confirmation", f"Supprimer {eleve.nom} {eleve.prenom} ?")
        if reponse != QMessageBox.Yes:
            return
        try:
            self.service.supprimer(eleve.id)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Suppression impossible", str(e))
            return
        self._remplir_classes()
        self.recharger()

    def _payer(self):
        eleve = self._eleve_selectionne()
        if not eleve:
            return
        if self.paiement_service.situation(eleve.id).solde == 0:
            QMessageBox.information(
                self, "Déjà soldé", f"{eleve.nom} {eleve.prenom} a déjà tout payé.")
            return
        PaiementDialog(self.paiement_service, eleve, self).exec()
        self.recharger()  