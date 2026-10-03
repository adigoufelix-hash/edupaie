import os
from pathlib import Path

from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.recu_pdf import generer_recu_pdf
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from edupaie.ui.paiement_dialog import MODES, PaiementDialog, fcfa
from edupaie.ui.style import preparer_table

LIBELLES_MODES = {valeur: libelle for libelle, valeur in MODES}
COULEURS = {"Soldé": "#2e7d32", "Partiellement payé": "#ef6c00",
            "Non payé": "#c62828"}


def date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


class FicheEleveDialog(QDialog):
    def __init__(self, paiement_service, eleve, parent=None):
        super().__init__(parent)
        self.service, self.eleve = paiement_service, eleve
        self.setWindowTitle(f"Fiche élève - {eleve.nom} {eleve.prenom}")
        self.resize(780, 480)

        self.entete = QLabel()
        self.entete.setObjectName("entete")
        self.entete.setTextFormat(Qt.RichText)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["N° de reçu", "Date", "Mode", "Montant", "Solde après"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)
        payer = QPushButton("Enregistrer un paiement")
        fermer = QPushButton("Fermer")
        boutons = QHBoxLayout()
        boutons.addWidget(payer)
        voir = QPushButton("Voir / imprimer le reçu")
        boutons.addWidget(voir)
        boutons.addStretch()
        boutons.addWidget(fermer)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(self.entete)
        mise_en_page.addWidget(QLabel("<b>Historique des paiements</b>"))
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(boutons)

        payer.clicked.connect(self._payer)
        fermer.clicked.connect(self.accept)
        voir.clicked.connect(self._recu)
        self.table.cellDoubleClicked.connect(lambda *_: self._recu())
        self.recharger()

    def recharger(self):
        e = self.eleve
        s = self.service.situation(e.id)
        couleur = COULEURS[s.statut]
        self.entete.setText(
            f"<h3>{e.nom} {e.prenom} - {e.classe} ({e.annee_scolaire})</h3>"
            f"<p>Total dû : <b>{fcfa(s.total_du)}</b> &nbsp;|&nbsp; "
            f"Payé : <b>{fcfa(s.total_paye)}</b> &nbsp;|&nbsp; "
            f"Solde : <b>{fcfa(s.solde)}</b> &nbsp;|&nbsp; "
            f"Statut : <b style='color:{couleur}'>{s.statut}</b></p>")
        paiements = self.service.historique(e.id)
        self.table.setRowCount(len(paiements))
        for ligne, p in enumerate(paiements):
            valeurs = [p.numero_recu, date_fr(p.date_paiement),
                       LIBELLES_MODES.get(p.mode, p.mode),
                       fcfa(p.montant), fcfa(p.solde_apres)]
            for col, texte in enumerate(valeurs):
                self.table.setItem(ligne, col, QTableWidgetItem(texte))
            self.table.item(ligne, 0).setData(Qt.UserRole, p.id)

    def _payer(self):
        if self.service.situation(self.eleve.id).solde == 0:
            QMessageBox.information(self, "Déjà soldé",
                                    "Cet élève a déjà tout payé.")
            return
        PaiementDialog(self.service, self.eleve, self).exec()
        self.recharger()
    def _recu(self):
        ligne = self.table.currentRow()
        if ligne < 0:
            QMessageBox.information(
                self, "Sélection", "Sélectionne d'abord un paiement dans la liste.")
            return
        paiement_id = self.table.item(ligne, 0).data(Qt.UserRole)
        try:
            eleve, paiement = self.service.recu(paiement_id)
            dossier = Path.home() / "EduPaie" / "recus"
            chemin = generer_recu_pdf(eleve, paiement, dossier)
            os.startfile(chemin)
        except (ErreurMetier, OSError) as e:
            QMessageBox.warning(self, "Reçu indisponible", str(e))