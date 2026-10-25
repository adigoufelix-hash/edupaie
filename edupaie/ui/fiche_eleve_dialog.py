from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.paiement_dialog import MODES, PaiementDialog, fcfa
from edupaie.ui.recu_action import ouvrir_recu
from edupaie.ui.remise_dialog import RemiseDialog
from edupaie.ui.style import preparer_table
from edupaie.ui.widgets import CarteKpi

LIBELLES_MODES = {valeur: libelle for libelle, valeur in MODES}
COULEURS = {"Soldé": "#166534", "Partiellement payé": "#9a3412",
            "Non payé": "#991b1b"}


def date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


def _table(colonnes):
    table = QTableWidget(0, len(colonnes))
    table.setHorizontalHeaderLabels(colonnes)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    preparer_table(table)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class FicheEleveDialog(QDialog):
    def __init__(self, paiement_service, eleve, parent=None, remise_service=None):
        super().__init__(parent)
        self.service, self.eleve = paiement_service, eleve
        self.remises = remise_service
        self.setWindowTitle(f"Fiche élève - {eleve.nom} {eleve.prenom}")
        self.resize(1000, 700)

        self.entete = QLabel()
        self.entete.setObjectName("entete")
        self.entete.setTextFormat(Qt.TextFormat.RichText)
        self.k_frais = CarteKpi("🎓", "Frais annuels", "#e0e7ff")
        self.k_regle = CarteKpi("✅", "Total réglé", "#dcfce7")
        self.k_solde = CarteKpi("⏳", "Solde restant", "#fef3c7")
        cartes = QHBoxLayout()
        for carte in (self.k_frais, self.k_regle, self.k_solde):
            cartes.addWidget(carte, 1)

        self.table = _table(["N° de reçu", "Date", "Mode", "Montant", "Solde après",
                             "Encaissé par", "État"])
        self.vide = QLabel("Aucun paiement enregistré pour cet élève.")
        self.vide.setObjectName("sousTitre")
        self.vide.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table_remises = _table(["Date", "Remise", "Montant", "Motif",
                                     "Accordée par", "État"])
        self.table_remises.setMaximumHeight(130)
        self.titre_remises = QLabel("<b>Remises et bourses</b>")

        payer = QPushButton("Enregistrer un paiement")
        voir = QPushButton("Voir / imprimer le reçu")
        annuler = QPushButton("Annuler le paiement")
        annuler.setObjectName("danger")
        if not self.service.peut_annuler():
            annuler.setEnabled(False)
            annuler.setToolTip("Réservé à l'administrateur")
        remise = QPushButton("Accorder une remise")
        annuler_remise = QPushButton("Annuler la remise")
        annuler_remise.setObjectName("danger")
        if self.remises is not None and not self.remises.peut_gerer():
            for bouton in (remise, annuler_remise):
                bouton.setEnabled(False)
                bouton.setToolTip("Réservé à l'administrateur")
        fermer = QPushButton("Fermer")

        boutons = QHBoxLayout()
        for bouton in (payer, voir, annuler, remise, annuler_remise):
            boutons.addWidget(bouton)
        boutons.addStretch()
        boutons.addWidget(fermer)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(self.entete)
        mise_en_page.addLayout(cartes)
        mise_en_page.addWidget(QLabel("<b>Historique des paiements</b>"))
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.vide)
        mise_en_page.addWidget(self.titre_remises)
        mise_en_page.addWidget(self.table_remises)
        mise_en_page.addLayout(boutons)

        if self.remises is None:  # écran lancé sans le service des remises
            for widget in (self.titre_remises, self.table_remises,
                           remise, annuler_remise):
                widget.hide()

        payer.clicked.connect(self._payer)
        voir.clicked.connect(self._recu)
        annuler.clicked.connect(self._annuler)
        remise.clicked.connect(self._accorder_remise)
        annuler_remise.clicked.connect(self._annuler_remise)
        fermer.clicked.connect(self.accept)
        self.table.cellDoubleClicked.connect(lambda *_: self._recu())
        self.recharger()

    def recharger(self):
        e = self.eleve
        s = self.service.situation(e.id)
        texte = (f"<h3 style='margin:0'>{e.nom} {e.prenom}</h3>"
                 f"<p style='margin:4px 0 0 0'>{e.classe} - {e.annee_scolaire} &nbsp; "
                 f"<b style='color:{COULEURS[s.statut]}'>{s.statut}</b>")
        if s.remise:
            texte += (f"<br>Frais : {fcfa(s.total_du + s.remise)} - "
                      f"remises : {fcfa(s.remise)}")
        self.entete.setText(texte + "</p>")
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
            for col, texte_cellule in enumerate(valeurs):
                item = QTableWidgetItem(texte_cellule)
                if p.annule:
                    self._barrer(item, col == 6)
                    item.setToolTip(
                        f"Annulé le {(p.annule_le or '')[:10]} par "
                        f"{p.annule_par or '-'}\nMotif : {p.motif_annulation or '-'}")
                self.table.setItem(ligne, col, item)
            self.table.item(ligne, 0).setData(Qt.UserRole, p.id)
        if self.remises is not None:
            self._recharger_remises()

    @staticmethod
    def _barrer(item, etat: bool):
        police = item.font()
        police.setStrikeOut(not etat)
        item.setFont(police)
        item.setForeground(QColor("#991b1b" if etat else "#9ca3af"))

    def _recharger_remises(self):
        remises = self.remises.lister(self.eleve.id)
        self.table_remises.setRowCount(len(remises))
        for i, r in enumerate(remises):
            genre = f"{r['valeur']} %" if r["type"] == "pourcentage" else "Montant fixe"
            valeurs = [date_fr(r["accorde_le"][:10]), genre, fcfa(r["montant"]),
                       r["motif"], r["accorde_par"] or "-",
                       "ANNULÉE" if r["annule"] else "Active"]
            for col, texte in enumerate(valeurs):
                item = QTableWidgetItem(texte)
                if r["annule"]:
                    self._barrer(item, col == 5)
                    item.setToolTip(
                        f"Annulée le {(r['annule_le'] or '')[:10]} par "
                        f"{r['annule_par'] or '-'}\nMotif : {r['motif_annulation'] or '-'}")
                self.table_remises.setItem(i, col, item)
            self.table_remises.item(i, 0).setData(Qt.UserRole, r["id"])

    def _payer(self):
        if self.service.situation(self.eleve.id).solde == 0:
            QMessageBox.information(self, "Déjà soldé",
                                    "Cet élève a déjà tout payé.")
            return
        PaiementDialog(self.service, self.eleve, self).exec()
        self.recharger()

    def _ligne_selectionnee(self, table, message):
        ligne = table.currentRow()
        if ligne < 0:
            QMessageBox.information(self, "Sélection", message)
            return None
        return ligne

    def _recu(self):
        ligne = self._ligne_selectionnee(
            self.table, "Sélectionne d'abord un paiement dans la liste.")
        if ligne is None:
            return
        ouvrir_recu(self, self.service, self.table.item(ligne, 0).data(Qt.UserRole))

    def _annuler(self):
        ligne = self._ligne_selectionnee(
            self.table, "Sélectionne d'abord un paiement dans la liste.")
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
            self.service.annuler_paiement(
                self.table.item(ligne, 0).data(Qt.UserRole), motif)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Annulation impossible", str(e))
            return
        self.recharger()

    def _accorder_remise(self):
        if self.service.situation(self.eleve.id).solde == 0:
            QMessageBox.information(self, "Remise",
                                    "Cet élève n'a plus rien à payer : pas de remise possible.")
            return
        if RemiseDialog(self.remises, self.eleve, self).exec() == QDialog.Accepted:
            self.recharger()

    def _annuler_remise(self):
        ligne = self._ligne_selectionnee(
            self.table_remises, "Sélectionne d'abord une remise dans la liste.")
        if ligne is None:
            return
        if self.table_remises.item(ligne, 5).text() == "ANNULÉE":
            QMessageBox.information(self, "Déjà annulée", "Cette remise est déjà annulée.")
            return
        motif, ok = QInputDialog.getText(
            self, "Annuler la remise",
            f"Remise de {self.table_remises.item(ligne, 2).text()} "
            f"({self.table_remises.item(ligne, 3).text()}).\n"
            "L'élève devra de nouveau cette somme.\n\n"
            "Motif de l'annulation (obligatoire) :")
        if not ok:
            return
        try:
            self.remises.annuler(self.table_remises.item(ligne, 0).data(Qt.UserRole), motif)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Annulation impossible", str(e))
            return
        self.recharger()