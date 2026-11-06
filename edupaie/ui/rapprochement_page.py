from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from edupaie.services import releve_import
from edupaie.services.export_rapprochement import exporter_rapprochement
from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.rapprochement_service import ETATS, OPERATEURS
from edupaie.ui.fichiers import apres_export
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table

COULEURS = {"rapproche": "#166534", "alerte": "#991b1b", "propose_ref": "#166534",
            "propose_sur": "#1d4ed8", "propose_probable": "#9a3412",
            "ecart": "#991b1b", "sans_paiement": "#991b1b", "ignore": "#6b7280"}


def date_fr(iso):
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


def _creer_table(colonnes):
    table = QTableWidget(0, len(colonnes))
    table.setHorizontalHeaderLabels(colonnes)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    preparer_table(table)
    return table


class ImportReleveDialog(QDialog):
    CHAMPS = [("date", "Date de l'opération"), ("montant", "Montant reçu"),
              ("reference", "N° de transaction"), ("libelle", "Expéditeur ou libellé"),
              ("sens", "Type d'opération")]

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.resultat = None
        self.lignes, self.entete, self.valides = [], 0, []
        self.setWindowTitle("Importer un relevé mobile money")
        self.resize(780, 660)

        self.fichier = QLabel("Aucun fichier choisi.")
        choisir = QPushButton("Choisir le fichier du relevé...")
        choisir.clicked.connect(self._choisir)
        self.operateur = QComboBox()
        self.operateur.addItems(OPERATEURS)
        formulaire = QFormLayout()
        formulaire.addRow("Opérateur", self.operateur)
        self.combos = {}
        for champ, libelle in self.CHAMPS:
            combo = QComboBox()
            combo.currentIndexChanged.connect(self._apercu)
            self.combos[champ] = combo
            formulaire.addRow(libelle, combo)
        self.filtre = QLineEdit()
        self.filtre.setPlaceholderText("ex. crédit (vide = tout garder)")
        self.filtre.textChanged.connect(self._apercu)
        formulaire.addRow("Garder seulement les opérations de type", self.filtre)

        aide = QLabel("EduPaie a deviné les colonnes : vérifie-les, surtout la date et le "
                      "montant <b>reçu</b> (pas un débit).")
        aide.setTextFormat(Qt.TextFormat.RichText)
        aide.setWordWrap(True)
        self.resume = QLabel()
        self.resume.setTextFormat(Qt.TextFormat.RichText)
        self.resume.setWordWrap(True)
        self.table = _creer_table(["Date", "Montant", "Référence", "Libellé"])
        self.bouton = QPushButton("Importer")
        self.bouton.setEnabled(False)
        self.bouton.clicked.connect(self._importer)
        annuler = QPushButton("Annuler")
        annuler.clicked.connect(self.reject)
        bas = QHBoxLayout()
        bas.addStretch()
        bas.addWidget(self.bouton)
        bas.addWidget(annuler)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(choisir)
        mise_en_page.addWidget(self.fichier)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(formulaire)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.table, 1)
        mise_en_page.addLayout(bas)

    def _choisir(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Relevé mobile money", "", "Relevés (*.xlsx *.xlsm *.csv *.txt)")
        if not chemin:
            return
        try:
            lignes = releve_import.lire_tableau(chemin)
        except (ErreurMetier, OSError) as e:
            QMessageBox.warning(self, "Fichier illisible", str(e))
            return
        if not lignes:
            QMessageBox.warning(self, "Fichier vide", "Ce fichier ne contient aucune ligne.")
            return
        self.lignes = lignes
        self.entete = releve_import.trouver_entete(lignes)
        self.fichier.setText(Path(chemin).name)
        entetes = [str(c if c is not None else "").strip() for c in lignes[self.entete]]
        trouve = releve_import.detecter_colonnes(entetes)
        for champ, combo in self.combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(aucune)")
            for i, titre in enumerate(entetes, start=1):
                combo.addItem(f"{i}. {titre or '(sans titre)'}")
            combo.setCurrentIndex(0 if trouve[champ] is None else trouve[champ] + 1)
            combo.blockSignals(False)
        self._apercu()

    def _colonnes(self):
        return {champ: (None if combo.currentIndex() <= 0 else combo.currentIndex() - 1)
                for champ, combo in self.combos.items()}

    def _apercu(self, *_):
        if not self.lignes:
            return
        colonnes = self._colonnes()
        self.valides = []
        if colonnes["date"] is None or colonnes["montant"] is None:
            self.resume.setText("Choisis au moins la colonne de la date et celle du montant.")
            self.table.setRowCount(0)
            self.bouton.setEnabled(False)
            return
        self.valides, ecartees = releve_import.normaliser(
            self.lignes, colonnes, self.entete + 1, self.filtre.text())
        texte = f"<b>{len(self.valides)}</b> opération(s) à importer"
        if ecartees:
            texte += (f" - {len(ecartees)} ligne(s) écartée(s) (par exemple la ligne "
                      f"{ecartees[0][0]} : {ecartees[0][1]})")
        self.resume.setText(texte)
        apercu = self.valides[:8]
        self.table.setRowCount(len(apercu))
        for i, l in enumerate(apercu):
            valeurs = (date_fr(l["date"]), fcfa(l["montant"]), l["reference"] or "",
                       l["libelle"] or "")
            for col, valeur in enumerate(valeurs):
                self.table.setItem(i, col, QTableWidgetItem(valeur))
        self.bouton.setEnabled(bool(self.valides))

    def _importer(self):
        try:
            self.resultat = self.service.importer(self.valides, self.operateur.currentText())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Import impossible", str(e))
            return
        QMessageBox.information(
            self, "Relevé importé",
            f"{self.resultat['importees']} opération(s) importée(s), "
            f"{self.resultat['doublons']} déjà présente(s) (ignorée(s)).")
        self.accept()


class ChoixPaiementDialog(QDialog):
    def __init__(self, candidats, parent=None):
        super().__init__(parent)
        self.candidats = candidats
        self.paiement_id = None
        self.setWindowTitle("Choisir le paiement")
        self.resize(640, 360)
        self.table = _creer_table(["Reçu", "Date", "Élève", "Classe", "Caissier"])
        self.table.setRowCount(len(candidats))
        for i, c in enumerate(candidats):
            for col, valeur in enumerate((c["numero_recu"], date_fr(c["date_paiement"]),
                                          c["eleve"], c["classe"], c["caissier"])):
                self.table.setItem(i, col, QTableWidgetItem(valeur))
        self.table.selectRow(0)
        valider = QPushButton("Rapprocher")
        valider.clicked.connect(self._valider)
        annuler = QPushButton("Annuler")
        annuler.clicked.connect(self.reject)
        bas = QHBoxLayout()
        bas.addStretch()
        bas.addWidget(valider)
        bas.addWidget(annuler)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(QLabel("Paiements mobile money du même montant, non rapprochés :"))
        mise_en_page.addWidget(self.table, 1)
        mise_en_page.addLayout(bas)

    def _valider(self):
        ligne = self.table.currentRow()
        if ligne < 0:
            return
        self.paiement_id = self.candidats[ligne]["id"]
        self.accept()


class RapprochementPage(QWidget):
    def __init__(self, service, dossier_exports="exports"):
        super().__init__()
        self.service = service
        self.dossier_exports = dossier_exports
        self.analyse = None

        self.debut, self.fin = QDateEdit(), QDateEdit()
        for champ in (self.debut, self.fin):
            champ.setCalendarPopup(True)
            champ.setDisplayFormat("dd/MM/yyyy")
        importer = QPushButton("Importer un relevé...")
        importer.clicked.connect(self._importer)
        tout = QPushButton("Tout le relevé")
        tout.clicked.connect(self._tout)
        exporter = QPushButton("Exporter en Excel")
        exporter.clicked.connect(self._exporter)
        haut = QHBoxLayout()
        haut.addWidget(importer)
        haut.addWidget(QLabel("Du"))
        haut.addWidget(self.debut)
        haut.addWidget(QLabel("au"))
        haut.addWidget(self.fin)
        haut.addWidget(tout)
        haut.addStretch()
        haut.addWidget(exporter)

        self.resume = QLabel()
        self.resume.setTextFormat(Qt.TextFormat.RichText)
        self.resume.setWordWrap(True)

        self.table = _creer_table(["Date", "Montant", "Référence", "Libellé", "État",
                                   "Paiement (reçu)", "Élève"])
        auto = QPushButton("Rapprocher automatiquement")
        valider = QPushButton("Valider la proposition")
        choisir = QPushButton("Choisir le paiement...")
        ignorer = QPushButton("Ignorer...")
        defaire = QPushButton("Annuler le rapprochement")
        auto.clicked.connect(self._auto)
        valider.clicked.connect(self._valider)
        choisir.clicked.connect(self._choisir)
        ignorer.clicked.connect(self._ignorer)
        defaire.clicked.connect(self._defaire)
        actions = QHBoxLayout()
        for bouton in (auto, valider, choisir, ignorer, defaire):
            actions.addWidget(bouton)
        actions.addStretch()
        page_releve = QWidget()
        colonne = QVBoxLayout(page_releve)
        colonne.addWidget(self.table)
        colonne.addLayout(actions)

        self.table_sans = _creer_table(["Reçu", "Date", "Montant", "Élève", "Classe", "Caissier"])
        aide = QLabel("Ces paiements sont enregistrés comme « mobile money » mais n'apparaissent "
                      "pas sur le relevé : l'argent est-il bien arrivé sur le compte ? À vérifier "
                      "auprès du caissier.")
        aide.setWordWrap(True)
        page_sans = QWidget()
        colonne2 = QVBoxLayout(page_sans)
        colonne2.addWidget(aide)
        colonne2.addWidget(self.table_sans)

        self.onglets = QTabWidget()
        self.onglets.addTab(page_releve, "Relevé")
        self.onglets.addTab(page_sans, "Paiements sans trace")

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.onglets, 1)

        self._regler_dates(*self.service.periode_par_defaut())
        self.debut.dateChanged.connect(self.recharger)
        self.fin.dateChanged.connect(self.recharger)
        self.recharger()

    # --- Période et affichage ----------------------------------------------------------------
    def _regler_dates(self, debut, fin):
        for champ, iso in ((self.debut, debut), (self.fin, fin)):
            champ.blockSignals(True)
            champ.setDate(QDate.fromString(iso, Qt.DateFormat.ISODate))
            champ.blockSignals(False)

    def _tout(self):
        self._regler_dates(*self.service.periode_par_defaut())
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()  # des paiements ont pu être saisis entre-temps

    def recharger(self, *_):
        try:
            self.analyse = self.service.analyser(
                self.debut.date().toString(Qt.DateFormat.ISODate),
                self.fin.date().toString(Qt.DateFormat.ISODate))
        except ErreurMetier as e:
            self.analyse = None
            self.resume.setText(f"<span style='color:#991b1b'>{e}</span>")
            return
        a, r = self.analyse, self.analyse["resume"]
        texte = (f"Relevé : <b>{fcfa(r['montant_releve'])}</b> ({r['nb_lignes']} opération(s)) - "
                 f"enregistré dans EduPaie en mobile money : <b>{fcfa(r['montant_enregistre'])}</b> "
                 f"({r['nb_enregistre']} paiement(s))<br>"
                 f"Rapprochées : {r['nb_rapproche']} ({fcfa(r['montant_rapproche'])}) - "
                 f"À valider : {r['nb_propose']} - "
                 f"<span style='color:#991b1b'>Sans paiement enregistré : {r['nb_sans_paiement']} "
                 f"({fcfa(r['montant_sans_paiement'])})</span> - "
                 f"<span style='color:#991b1b'>Paiements sans trace : {r['nb_sans_trace']} "
                 f"({fcfa(r['montant_sans_trace'])})</span>")
        if r["nb_alertes"]:
            texte += (f"<br><b style='color:#991b1b'>⚠ {r['nb_alertes']} paiement(s) rapproché(s) "
                      "puis annulé(s) : à vérifier.</b>")
        if not a["lignes"]:
            texte += "<br>Aucune opération sur cette période : importe un relevé."
        self.resume.setText(texte)
        self._remplir_releve(a["lignes"])
        self._remplir_sans_trace(a["sans_trace"])
        self.onglets.setTabText(0, f"Relevé ({len(a['lignes'])})")
        self.onglets.setTabText(1, f"Paiements sans trace ({len(a['sans_trace'])})")

    def _remplir_releve(self, lignes):
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            p = l["paiement"] or l["proposition"] or {}
            recu = p.get("numero_recu", "")
            if l["proposition"] and l["proposition"]["alternatives"]:
                recu += f" (+{l['proposition']['alternatives']} autre(s) possible(s))"
            valeurs = (date_fr(l["date"]), fcfa(l["montant"]), l["reference"], l["libelle"],
                       ETATS[l["etat"]] + (f" : {l['motif']}" if l["motif"] else ""), recu,
                       p.get("eleve", ""))
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if col == 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 4:
                    item.setForeground(QColor(COULEURS[l["etat"]]))
                    police = item.font()
                    police.setBold(True)
                    item.setFont(police)
                self.table.setItem(i, col, item)

    def _remplir_sans_trace(self, paiements):
        self.table_sans.setRowCount(len(paiements))
        for i, p in enumerate(paiements):
            valeurs = (p["numero_recu"], date_fr(p["date_paiement"]), fcfa(p["montant"]),
                       p["eleve"], p["classe"], p["caissier"])
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if col == 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_sans.setItem(i, col, item)

    # --- Actions -----------------------------------------------------------------------------------
    def _selection(self):
        ligne = self.table.currentRow()
        if self.analyse is None or ligne < 0:
            QMessageBox.information(self, "Rapprochement",
                                    "Sélectionne d'abord une opération du relevé.")
            return None
        return self.analyse["lignes"][ligne]

    def _a_traiter(self, ligne):
        if ligne["etat"] in ("propose_ref", "propose_sur", "propose_probable", "ecart",
                             "sans_paiement"):
            return True
        QMessageBox.information(self, "Rapprochement",
                                "Cette opération est déjà traitée : annule d'abord son "
                                "rapprochement si tu veux la modifier.")
        return False

    def _executer(self, action, *arguments):
        try:
            action(*arguments)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Rapprochement impossible", str(e))
            return False
        self.recharger()
        return True

    def _importer(self):
        dialogue = ImportReleveDialog(self.service, self)
        if dialogue.exec() != QDialog.Accepted or not dialogue.resultat:
            return
        self._regler_dates(*self.service.periode_par_defaut())
        self.recharger()

    def _auto(self):
        if self.analyse is None:
            return
        try:
            resultat = self.service.rapprocher_automatiquement(
                self.analyse["debut"], self.analyse["fin"])
        except ErreurMetier as e:
            QMessageBox.warning(self, "Rapprochement impossible", str(e))
            return
        self.recharger()
        QMessageBox.information(
            self, "Rapprochement automatique",
            f"{resultat['rapproches']} opération(s) rapprochée(s). Les correspondances "
            "« probables » restent à valider une par une.")

    def _valider(self):
        ligne = self._selection()
        if ligne is None or not self._a_traiter(ligne):
            return
        if ligne["proposition"] is None:
            QMessageBox.information(self, "Rapprochement",
                                    "Aucune proposition pour cette opération : utilise « Choisir "
                                    "le paiement... » ou « Ignorer... ».")
            return
        self._executer(self.service.rapprocher, ligne["id"], ligne["proposition"]["paiement_id"])

    def _choisir(self):
        ligne = self._selection()
        if ligne is None or not self._a_traiter(ligne):
            return
        try:
            candidats = self.service.candidats(ligne["id"])
        except ErreurMetier as e:
            QMessageBox.warning(self, "Rapprochement", str(e))
            return
        if not candidats:
            QMessageBox.information(
                self, "Aucun paiement",
                f"Aucun paiement mobile money de {fcfa(ligne['montant'])} non rapproché autour de "
                "cette date. Regarde l'onglet « Paiements sans trace » : le caissier a peut-être "
                "saisi un autre montant.")
            return
        dialogue = ChoixPaiementDialog(candidats, self)
        if dialogue.exec() == QDialog.Accepted and dialogue.paiement_id:
            self._executer(self.service.rapprocher, ligne["id"], dialogue.paiement_id)

    def _ignorer(self):
        ligne = self._selection()
        if ligne is None or not self._a_traiter(ligne):
            return
        motif, ok = QInputDialog.getText(
            self, "Ignorer l'opération",
            "Pourquoi ignorer cette opération ? (ex. virement personnel du directeur)")
        if ok:
            self._executer(self.service.ignorer, ligne["id"], motif)

    def _defaire(self):
        ligne = self._selection()
        if ligne is None:
            return
        if ligne["etat"] not in ("rapproche", "alerte", "ignore", "ecart"):
            QMessageBox.information(self, "Rapprochement",
                                    "Cette opération n'est ni rapprochée ni ignorée.")
            return
        if QMessageBox.question(self, "Annuler",
                                "Remettre cette opération à traiter ?") == QMessageBox.Yes:
            self._executer(self.service.defaire, ligne["id"])

    def _exporter(self):
        if self.analyse is None or not self.analyse["lignes"]:
            QMessageBox.information(self, "Rapprochement", "Rien à exporter sur cette période.")
            return
        try:
            chemin = exporter_rapprochement(self.analyse, self.dossier_exports)
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        apres_export(self, chemin)