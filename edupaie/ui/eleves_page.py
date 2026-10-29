from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QHBoxLayout,
                               QHeaderView, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from edupaie.services.export_excel import exporter_eleves
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.eleve_dialog import EleveDialog
from edupaie.ui.fiche_eleve_dialog import FicheEleveDialog
from edupaie.ui.fichiers import apres_export
from edupaie.ui.import_dialog import ImportDialog
from edupaie.ui.paiement_dialog import PaiementDialog
from edupaie.ui.style import preparer_table
from edupaie.ui.widgets import cellule_pastille


def fcfa(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ") + " FCFA"


class ElevesPage(QWidget):
    def __init__(self, service, paiement_service, auth, frais_service=None,
                 remise_service=None, echeancier_service=None, import_service=None):
        super().__init__()
        self.service = service
        self.frais = frais_service
        self.remises = remise_service
        self.echeancier = echeancier_service
        self.import_service = import_service
        self._situations = []
        self.paiement_service = paiement_service
        self.auth = auth
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
        preparer_table(self.table)
        entete = self.table.horizontalHeader()
        for col in (3, 4, 5, 6, 7):
            entete.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        ajouter = QPushButton("Ajouter")
        modifier = QPushButton("Modifier")
        supprimer = QPushButton("Supprimer")
        supprimer.setObjectName("danger")
        payer = QPushButton("Enregistrer un paiement")
        fiche = QPushButton("Fiche et Historique")
        excel = QPushButton("Exporter vers Excel")
        importer = QPushButton("Importer depuis Excel")
        if import_service is None:
            importer.hide()

        haut, bas = QHBoxLayout(), QHBoxLayout()
        haut.addWidget(self.recherche, 1)
        haut.addWidget(self.filtre)
        haut.addWidget(self.filtre_statut)
        for b in (ajouter, modifier, supprimer, payer, fiche, excel, importer):
            bas.addWidget(b)

        # Les boutons interdits au rôle de l'utilisateur connecté sont désactivés
        droits = ((ajouter, "eleve.ecrire"), (modifier, "eleve.ecrire"),
                  (supprimer, "eleve.supprimer"), (payer, "paiement.encaisser"),
                  (importer, "eleve.importer"))
        for bouton, permission in droits:
            if not self.auth.peut(permission):
                bouton.setEnabled(False)
                bouton.setToolTip("Non autorisé pour votre rôle")

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
        payer.clicked.connect(self._payer)
        fiche.clicked.connect(self._fiche)
        excel.clicked.connect(self._exporter_excel)
        importer.clicked.connect(self._importer)
        self.table.cellDoubleClicked.connect(lambda *_: self._fiche())
        self._remplir_classes()
        self.recharger()

    def _autorise(self, permission: str) -> bool:
        if self.auth.peut(permission):
            return True
        QMessageBox.warning(self, "Accès refusé",
                            "Votre rôle ne permet pas cette action.")
        return False

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
        self._situations = situations
        self.table.setRowCount(len(situations))
        for ligne, (e, s) in enumerate(situations):
            valeurs = [e.nom, e.prenom, e.classe, e.annee_scolaire,
                       fcfa(s.total_du), fcfa(s.total_paye), fcfa(s.solde)]
            for col, texte in enumerate(valeurs):
                self.table.setItem(ligne, col, QTableWidgetItem(texte))
            self.table.item(ligne, 0).setData(Qt.UserRole, e.id)
            self.table.setCellWidget(ligne, 7, cellule_pastille(s.statut))

    def _eleve_selectionne(self):
        ligne = self.table.currentRow()
        if ligne < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord un élève.")
            return None
        eleve_id = self.table.item(ligne, 0).data(Qt.UserRole)
        return next(e for e in self.service.lister() if e.id == eleve_id)

    def _ajouter(self):
        if not self._autorise("eleve.ecrire"):
            return
        if EleveDialog(self.service, parent=self, frais=self.frais).exec() == QDialog.Accepted:
            self._remplir_classes()
            self.recharger()

    def _modifier(self):
        if not self._autorise("eleve.ecrire"):
            return
        eleve = self._eleve_selectionne()
        if eleve and EleveDialog(self.service, eleve, self, frais=self.frais).exec():
            self._remplir_classes()
            self.recharger()

    def _supprimer(self):
        if not self._autorise("eleve.supprimer"):
            return
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
        if not self._autorise("paiement.encaisser"):
            return
        eleve = self._eleve_selectionne()
        if not eleve:
            return
        if self.paiement_service.situation(eleve.id).solde == 0:
            QMessageBox.information(
                self, "Déjà soldé", f"{eleve.nom} {eleve.prenom} a déjà tout payé.")
            return
        PaiementDialog(self.paiement_service, eleve, self).exec()
        self.recharger()

    def _fiche(self):
        eleve = self._eleve_selectionne()
        if not eleve:
            return
        FicheEleveDialog(self.paiement_service, eleve, self,
                         remise_service=self.remises,
                         echeancier_service=self.echeancier).exec()
        self.recharger()

    def _exporter_excel(self):
        if not self._situations:
            QMessageBox.information(self, "Export", "Aucun élève à exporter.")
            return
        try:
            chemin = exporter_eleves(self._situations, "exports")
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        apres_export(self, chemin)

    def _importer(self):
        if not self._autorise("eleve.importer"):
            return
        if ImportDialog(self.import_service, self).exec() == QDialog.Accepted:
            self._remplir_classes()
            self.recharger()