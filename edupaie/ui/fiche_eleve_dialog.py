import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.recu_pdf import generer_recu_pdf
from edupaie.ui.paiement_dialog import MODES, PaiementDialog, fcfa
from edupaie.ui.style import preparer_table
from edupaie.ui.widgets import CarteKpi

LIBELLES_MODES = {valeur: libelle for libelle, valeur in MODES}
COULEURS = {"Soldé": "#166534", "Partiellement payé": "#9a3412",
            "Non payé": "#991b1b"}


def date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


class FicheEleveDialog(QDialog):
    def __init__(self, paiement_service, eleve, parent=None):
        super().__init__(parent)
        self.service, self.eleve = paiement_service, eleve
        self.setWindowTitle(f"Fiche élève - {eleve.nom} {eleve.prenom}")
        self.resize(820, 560)

        self.entete = QLabel()
        self.entete.setObjectName("entete")
        self.entete.setTextFormat(Qt.TextFormat.RichText)
        self.k_frais = CarteKpi("🎓", "Frais annuels", "#e0e7ff")
        self.k_regle = CarteKpi("✅", "Total réglé", "#dcfce7")
        self.k_solde = CarteKpi("⏳", "Solde restant", "#fef3c7")
        cartes = QHBoxLayout()
        for carte in (self.k_frais, self.k_regle, self.k_solde):
            cartes.addWidget(carte, 1)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["N° de reçu", "Date", "Mode", "Montant", "Solde après"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        preparer_table(self.table)
        self.vide = QLabel("Aucun paiement enregistré pour cet élève.")
        self.vide.setObjectName("sousTitre")
        self.vide.setAlignment(Qt.AlignmentFlag.AlignCenter)

        payer = QPushButton("Enregistrer un paiement")
        voir = QPushButton("Voir / imprimer le reçu")
        fermer = QPushButton("Fermer")
        boutons = QHBoxLayout()
        boutons.addWidget(payer)
        boutons.addWidget(voir)
        boutons.addStretch()
        boutons.addWidget(fermer)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(self.entete)
        mise_en_page.addLayout(cartes)
        mise_en_page.addWidget(QLabel("<b>Historique des paiements</b>"))
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(boutons)

        payer.clicked.connect(self._payer)
        voir.clicked.connect(self._recu)
        fermer.clicked.connect(self.accept)
        self.table.cellDoubleClicked.connect(lambda *_: self._recu())
        self.recharger()

    def recharger(self):
        e = self.eleve
        s = self.service.situation(e.id)
        self.entete.setText(
            f"<h3 style='margin:0'>{e.nom} {e.prenom}</h3>"
            f"<p style='margin:4px 0 0 0'>{e.classe} - {e.annee_scolaire} &nbsp; "
            f"<b style='color:{COULEURS[s.statut]}'>{s.statut}</b></p>")
        self.k_frais.maj(fcfa(s.total_du))
        self.k_regle.maj(fcfa(s.total_paye))
        self.k_solde.maj(fcfa(s.solde))
        paiements = self.service.historique(e.id)
        self.vide.setVisible(not paiements)
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