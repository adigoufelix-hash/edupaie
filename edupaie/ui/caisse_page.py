from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.services.cloture_pdf import generer_cloture_pdf
from edupaie.services.export_excel import exporter_cloture
from edupaie.services.paiement_service import MODES, ErreurMetier
from edupaie.ui.fichiers import apres_export
from edupaie.ui.paiement_dialog import MODES as MODES_UI
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table

LIBELLES_MODES = {valeur: libelle for libelle, valeur in MODES_UI}


class CaissePage(QWidget):
    def __init__(self, service, dossier_pdf="clotures"):
        super().__init__()
        self.service = service
        self.dossier_pdf = dossier_pdf
        self.cloture = None

        aujourdhui = QDate.currentDate()
        self.debut, self.fin = QDateEdit(aujourdhui), QDateEdit(aujourdhui)
        for champ in (self.debut, self.fin):
            champ.setCalendarPopup(True)
            champ.setDisplayFormat("dd/MM/yyyy")
        jour = QPushButton("Aujourd'hui")
        mois = QPushButton("Ce mois")
        jour.clicked.connect(lambda: self._periode(aujourdhui, aujourdhui))
        mois.clicked.connect(lambda: self._periode(
            QDate(aujourdhui.year(), aujourdhui.month(), 1), aujourdhui))

        self.resume = QLabel()
        self.resume.setTextFormat(Qt.TextFormat.RichText)
        self.resume.setWordWrap(True)

        colonnes = ["Caissier", "Paiements"] + [
            LIBELLES_MODES.get(m, m) for m in MODES] + ["Total"]
        self.table = QTableWidget(0, len(colonnes))
        self.table.setHorizontalHeaderLabels(colonnes)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        exporter = QPushButton("Exporter en PDF")
        exporter.clicked.connect(self._exporter)
        excel = QPushButton("Exporter en Excel")
        excel.clicked.connect(self._exporter_excel)

        haut = QHBoxLayout()
        haut.addWidget(QLabel("Du"))
        haut.addWidget(self.debut)
        haut.addWidget(QLabel("au"))
        haut.addWidget(self.fin)
        haut.addWidget(jour)
        haut.addWidget(mois)
        haut.addStretch()
        haut.addWidget(exporter)
        haut.addWidget(excel)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.table)

        self.debut.dateChanged.connect(self.recharger)
        self.fin.dateChanged.connect(self.recharger)
        self.recharger()

    def _periode(self, debut, fin):
        self.debut.setDate(debut)
        self.fin.setDate(fin)

    @staticmethod
    def _iso(champ) -> str:
        return champ.date().toString(Qt.DateFormat.ISODate)

    def recharger(self, *_):
        try:
            self.cloture = self.service.cloture(self._iso(self.debut), self._iso(self.fin))
        except ErreurMetier as e:
            self.cloture = None
            self.table.setRowCount(0)
            self.resume.setText(f"<span style='color:#991b1b'>{e}</span>")
            return
        c = self.cloture
        texte = f"{c['portee']}<br>"
        if c["nb"]:
            texte += f"<b>{fcfa(c['total'])}</b> encaissés - {c['nb']} paiement(s)"
        else:
            texte += "Aucun paiement sur cette période."
        if c["annules"]["nb"]:
            texte += (f"<br><span style='color:#991b1b'>{c['annules']['nb']} paiement(s) "
                      f"annulé(s) ({fcfa(c['annules']['total'])} non compté)</span>")
        self.resume.setText(texte)

        lignes = [(cais["nom"], cais["nb"], cais["par_mode"], cais["total"], False)
                  for cais in c["caissiers"]]
        if lignes:
            lignes.append(("TOTAL", c["nb"], c["par_mode"], c["total"], True))
        self.table.setRowCount(len(lignes))
        for i, (nom, nb, par_mode, total, gras) in enumerate(lignes):
            valeurs = [nom, str(nb)] + [fcfa(par_mode[m]) for m in MODES] + [fcfa(total)]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if gras:
                    police = item.font()
                    police.setBold(True)
                    item.setFont(police)
                self.table.setItem(i, col, item)

    def _vide(self) -> bool:
        c = self.cloture
        if c is None:
            QMessageBox.information(self, "Clôture", "Choisis d'abord une période valide.")
            return True
        if not c["nb"] and not c["annules"]["nb"]:
            QMessageBox.information(
                self, "Clôture", "Aucun paiement sur cette période : rien à exporter.")
            return True
        return False

    def _exporter(self):
        if self._vide():
            return
        try:
            chemin = generer_cloture_pdf(self.cloture, self.dossier_pdf)
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin.resolve())))

    def _exporter_excel(self):
        if self._vide():
            return
        try:
            chemin = exporter_cloture(self.cloture, "exports")
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        apres_export(self, chemin)