from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.paiement_dialog import MODES, PaiementDialog, fcfa
from edupaie.ui.recu_action import ouvrir_recu
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
        self.resize(980, 580)

        self.entete = QLabel()
        self.entete.setObjectName("entete")
        self.entete.setTextFormat(Qt.TextFormat.RichText)
        self.k_frais = CarteKpi("🎓", "Frais annuels", "#e0e7ff")
        self.k_regle = CarteKpi("✅", "Total réglé", "#dcfce7")
        self.k_solde = CarteKpi("⏳", "Solde restant", "#fef3c7")
        cartes = QHBoxLayout()
        for carte in (self.k_frais, self.k_regle, self.k_solde):
            cartes.addWidget(carte, 1)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["N° de reçu", "Date", "Mode", "Montant", "Solde après",
             "Encaissé par", "État"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        preparer_table(self.table)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.vide = QLabel("Aucun paiement enregistré pour cet élève.")
        self.vide.setObjectName("sousTitre")
        self.vide.setAlignment(Qt.AlignmentFlag.AlignCenter)

        payer = QPushButton("Enregistrer un paiement")
        voir = QPushButton("Voir / imprimer le reçu")
        annuler = QPushButton("Annuler le paiement")
        annuler.setObjectName("danger")
        if not self.service.peut_annuler():
            annuler.setEnabled(False)
            annuler.setToolTip("Réservé à l'administrateur")
        fermer = QPushButton("Fermer")
        boutons = QHBoxLayout()
        boutons.addWidget(payer)
        boutons.addWidget(voir)
        boutons.addWidget(annuler)
        boutons.addStretch()
        boutons.addWidget(fermer)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(self.entete)
        mise_en_page.addLayout(cartes)
        mise_en_page.addWidget(QLabel("<b>Historique des paiements</b>"))
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.vide)
        mise_en_page.addLayout(boutons)

        payer.clicked.connect(self._payer)
        voir.clicked.connect(self._recu)
        annuler.clicked.connect(self._annuler)
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
                       fcfa(p.montant), fcfa(p.solde_apres),
                       p.encaisse_par or "-",
                       "ANNULÉ" if p.annule else "Valide"]
            for col, texte in enumerate(valeurs):
                item = QTableWidgetItem(texte)
                if p.annule:
                    police = item.font()
                    police.setStrikeOut(col != 6)
                    item.setFont(police)
                    item.setForeground(QColor("#991b1b" if col == 6 else "#9ca3af"))
                    item.setToolTip(
                        f"Annulé le {(p.annule_le or '')[:10]} par "
                        f"{p.annule_par or '-'}\nMotif : {p.motif_annulation or '-'}")
                self.table.setItem(ligne, col, item)
            self.table.item(ligne, 0).setData(Qt.UserRole, p.id)

    def _payer(self):
        if self.service.situation(self.eleve.id).solde == 0:
            QMessageBox.information(self, "Déjà soldé",
                                    "Cet élève a déjà tout payé.")
            return
        PaiementDialog(self.service, self.eleve, self).exec()
        self.recharger()

    def _paiement_selectionne(self):
        ligne = self.table.currentRow()
        if ligne < 0:
            QMessageBox.information(
                self, "Sélection", "Sélectionne d'abord un paiement dans la liste.")
            return None
        return ligne

    def _recu(self):
        ligne = self._paiement_selectionne()
        if ligne is None:
            return
        ouvrir_recu(self, self.service, self.table.item(ligne, 0).data(Qt.UserRole))

    def _annuler(self):
        ligne = self._paiement_selectionne()
        if ligne is None:
            return
        if self.table.item(ligne, 6).text() == "ANNULÉ":
            QMessageBox.information(self, "Déjà annulé", "Ce paiement est déjà annulé.")
            return
        numero = self.table.item(ligne, 0).text()
        montant = self.table.item(ligne, 3).text()
        motif, ok = QInputDialog.getText(
            self, "Annuler le paiement",
            f"Reçu {numero} ({montant}).\n"
            "Cette action est définitive : le paiement restera visible mais ne sera "
            "plus compté.\n\nMotif de l'annulation (obligatoire) :")
        if not ok:
            return
        try:
            self.service.annuler_paiement(self.table.item(ligne, 0).data(Qt.UserRole), motif)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Annulation impossible", str(e))
            return
        self.recharger()