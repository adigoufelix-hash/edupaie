from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.services.export_excel import exporter_impayes
from edupaie.services.impayes_pdf import generer_impayes_pdf
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.contact_dialog import ContactDialog
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table
from edupaie.ui.fichiers import apres_export


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


class ImpayesPage(QWidget):
    def __init__(self, service, dossier_pdf="impayes", dossier_excel="exports"):
        super().__init__()
        self.service = service
        self.dossier_pdf, self.dossier_excel = dossier_pdf, dossier_excel
        self.resultat = None

        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.classe = QComboBox()
        self.classe.addItem("Toutes les classes", None)
        for c in service.classes():
            self.classe.addItem(c, c)

        self.resume = QLabel()
        self.resume.setTextFormat(Qt.TextFormat.RichText)
        self.resume.setWordWrap(True)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Élève", "Classe", "Échéance impayée", "Date limite", "Jours",
             "Exigible", "Payé", "En retard", "Téléphone"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        whatsapp = QPushButton("Relancer par WhatsApp")
        contact = QPushButton("Modifier le contact")
        pdf = QPushButton("Exporter en PDF")
        excel = QPushButton("Exporter en Excel")
        if not service.peut_modifier_contact():
            contact.setEnabled(False)
            contact.setToolTip("Non autorisé pour votre rôle")
        whatsapp.clicked.connect(self._whatsapp)
        contact.clicked.connect(self._contact)
        pdf.clicked.connect(self._exporter_pdf)
        excel.clicked.connect(self._exporter_excel)

        haut = QHBoxLayout()
        haut.addWidget(QLabel("En retard au"))
        haut.addWidget(self.date)
        haut.addWidget(self.classe, 1)
        bas = QHBoxLayout()
        for b in (whatsapp, contact, pdf, excel):
            bas.addWidget(b)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.table)
        mise_en_page.addLayout(bas)

        self.date.dateChanged.connect(self.recharger)
        self.classe.currentIndexChanged.connect(self.recharger)
        self.recharger()

    def _iso(self) -> str:
        return self.date.date().toString(Qt.DateFormat.ISODate)

    def recharger(self, *_):
        try:
            self.resultat = self.service.impayes(self._iso(), self.classe.currentData())
        except ErreurMetier as e:
            self.resultat = None
            self.table.setRowCount(0)
            self.resume.setText(f"<span style='color:#991b1b'>{e}</span>")
            return
        r = self.resultat
        lignes = r["lignes"]
        if lignes:
            texte = f"<b>{fcfa(r['total_retard'])}</b> en retard - {len(lignes)} élève(s)"
        else:
            texte = "Aucun élève en retard à cette date."
        if r["sans_echeancier"]:
            texte += (f"<br>{r['sans_echeancier']} élève(s) sont dans des classes sans "
                      "échéancier (non suivis).")
        self.resume.setText(texte)
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            valeurs = [l["nom"], l["classe"], l["tranche"], _date_fr(l["date_limite"]),
                       str(l["jours"]), fcfa(l["exigible"]), fcfa(l["paye"]),
                       fcfa(l["retard"]), l["telephone"] or "-"]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if col == 7:
                    item.setForeground(QColor("#991b1b"))
                self.table.setItem(i, col, item)

    def _ligne(self):
        i = self.table.currentRow()
        if self.resultat is None or i < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord un élève.")
            return None
        return self.resultat["lignes"][i]

    def _whatsapp(self):
        ligne = self._ligne()
        if ligne is None:
            return
        lien = self.service.lien_whatsapp(ligne)
        if lien is None:
            QMessageBox.information(
                self, "WhatsApp",
                "Aucun numéro valide pour ce parent : renseigne d'abord le contact.")
            self._contact()
            return
        QDesktopServices.openUrl(QUrl(lien))

    def _contact(self):
        ligne = self._ligne()
        if ligne is None:
            return
        if ContactDialog(self.service, ligne["eleve_id"], ligne["nom"],
                         self).exec():
            self.recharger()

    def _vide(self) -> bool:
        if self.resultat is None or not self.resultat["lignes"]:
            QMessageBox.information(self, "Export", "Aucun impayé à exporter.")
            return True
        return False

    def _exporter(self, fonction, dossier):
        if self._vide():
            return
        try:
            chemin = fonction(self.resultat, dossier)
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        apres_export(self, chemin)
    def _exporter_pdf(self):
        self._exporter(generer_impayes_pdf, self.dossier_pdf)

    def _exporter_excel(self):
        self._exporter(exporter_impayes, self.dossier_excel)