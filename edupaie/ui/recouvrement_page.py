from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QFrame, QHBoxLayout,
                               QLabel, QMessageBox, QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.services.export_recouvrement import exporter_recouvrement
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.fichiers import apres_export
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table


def _carte(titre, fond):
    cadre = QFrame()
    cadre.setObjectName("kpi")
    cadre.setStyleSheet(f"QFrame#kpi {{ background: {fond}; border-radius: 12px; }}")
    intitule = QLabel(titre)
    intitule.setStyleSheet("background: transparent; font-weight: bold;")
    valeur = QLabel("-")
    valeur.setStyleSheet("background: transparent; font-size: 22px; font-weight: bold;")
    detail = QLabel("")
    detail.setWordWrap(True)
    detail.setStyleSheet("background: transparent;")
    colonne = QVBoxLayout(cadre)
    colonne.addWidget(intitule)
    colonne.addWidget(valeur)
    colonne.addWidget(detail)
    return cadre, valeur, detail


def _barre(taux):
    barre = QProgressBar()
    barre.setRange(0, 100)
    barre.setValue(int(min(round(taux), 100)))
    barre.setFormat(f"{taux:.1f} %")
    couleur = "#16a34a" if taux >= 80 else "#d97706" if taux >= 50 else "#dc2626"
    barre.setStyleSheet(
        "QProgressBar { border: 1px solid #d1d5db; border-radius: 6px; text-align: center; }"
        f"QProgressBar::chunk {{ background: {couleur}; border-radius: 5px; }}")
    return barre


def _creer_table(colonnes):
    table = QTableWidget(0, len(colonnes))
    table.setHorizontalHeaderLabels(colonnes)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    preparer_table(table)
    return table


class RecouvrementPage(QWidget):
    def __init__(self, service, dossier_exports="exports"):
        super().__init__()
        self.service = service
        self.dossier_exports = dossier_exports
        self.donnees = None

        self.annee = QComboBox()
        self.date_ref = QDateEdit(QDate.currentDate())
        self.date_ref.setCalendarPopup(True)
        self.date_ref.setDisplayFormat("dd/MM/yyyy")
        exporter = QPushButton("Exporter en Excel")
        exporter.clicked.connect(self._exporter)
        haut = QHBoxLayout()
        haut.addWidget(QLabel("Année scolaire"))
        haut.addWidget(self.annee)
        haut.addWidget(QLabel("Situation au"))
        haut.addWidget(self.date_ref)
        haut.addStretch()
        haut.addWidget(exporter)

        self.k_taux = _carte("Taux d'encaissement", "#e0e7ff")
        self.k_reste = _carte("Reste à encaisser", "#fef3c7")
        self.k_du = _carte("Payé sur ce qui était dû", "#dcfce7")
        self.k_retard = _carte("En retard", "#fee2e2")
        cartes = QHBoxLayout()
        for carte in (self.k_taux, self.k_reste, self.k_du, self.k_retard):
            cartes.addWidget(carte[0], 1)

        self.table_classes = _creer_table(
            ["Classe", "Élèves", "À payer", "Encaissé", "Reste", "Taux d'encaissement",
             "En retard", "Élèves en retard"])
        self.table_mois = _creer_table(
            ["Mois", "Encaissé", "Prévu (échéances)", "Taux du mois", "Encaissé cumulé",
             "Prévu cumulé"])
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.TextFormat.RichText)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addLayout(cartes)
        mise_en_page.addWidget(QLabel("<b>Par classe</b>"))
        mise_en_page.addWidget(self.table_classes, 3)
        mise_en_page.addWidget(QLabel("<b>Par mois</b>"))
        mise_en_page.addWidget(self.table_mois, 2)
        mise_en_page.addWidget(self.note)

        self.annee.currentTextChanged.connect(self.recharger)
        self.date_ref.dateChanged.connect(self.recharger)
        self._charger_annees()

    def showEvent(self, event):
        super().showEvent(event)
        self._charger_annees()  # des paiements ou des élèves ont pu changer

    def _charger_annees(self):
        try:
            annees = self.service.annees()
        except ErreurMetier as e:
            self.note.setText(f"<span style='color:#991b1b'>{e}</span>")
            return
        garde = self.annee.currentText()
        self.annee.blockSignals(True)
        self.annee.clear()
        self.annee.addItems(annees)
        if garde in annees:
            self.annee.setCurrentText(garde)
        self.annee.blockSignals(False)
        self.recharger()

    def recharger(self, *_):
        annee = self.annee.currentText()
        if not annee:
            self.donnees = None
            self.table_classes.setRowCount(0)
            self.table_mois.setRowCount(0)
            self.note.setText("Aucun élève enregistré : le tableau se remplira avec les "
                              "premiers élèves et paiements.")
            return
        try:
            self.donnees = self.service.tableau(
                annee, self.date_ref.date().toString(Qt.DateFormat.ISODate))
        except ErreurMetier as e:
            QMessageBox.warning(self, "Recouvrement", str(e))
            return
        d = self.donnees
        self._maj_cartes(d["total"])
        self._remplir_classes(d)
        self._remplir_mois(d)
        texte = ("Le « prévu » vient de l'échéancier de chaque classe. Les paiements annulés "
                 "ne sont pas comptés.")
        if d["classes_sans_echeancier"]:
            texte += ("<br><span style='color:#9a3412'>Sans échéancier (ni prévu ni retard) : "
                      + ", ".join(d["classes_sans_echeancier"]) + ".</span>")
        self.note.setText(texte)

    def _maj_cartes(self, t):
        taux = "-" if t["taux"] is None else f"{t['taux']:.1f} %"
        self.k_taux[1].setText(taux)
        self.k_taux[2].setText(f"{fcfa(t['paye'])} encaissés sur {fcfa(t['net'])} à payer")
        self.k_reste[1].setText(fcfa(t["reste"]))
        self.k_reste[2].setText(f"{t['eleves']} élève(s) dont {t['soldes']} soldé(s)")
        self.k_du[1].setText("-" if t["taux_exigible"] is None
                             else f"{t['taux_exigible']:.1f} %")
        self.k_du[2].setText(f"Exigible à cette date : {fcfa(t['exigible'])}")
        self.k_retard[1].setText(fcfa(t["retard"]))
        self.k_retard[2].setText(f"{t['en_retard']} élève(s) en retard")

    @staticmethod
    def _item(texte, droite=False, gras=False, couleur=None):
        item = QTableWidgetItem(str(texte))
        if droite:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if gras:
            police = item.font()
            police.setBold(True)
            item.setFont(police)
        if couleur:
            item.setForeground(Qt.GlobalColor.darkGray)
        return item

    def _remplir_classes(self, d):
        lignes = d["classes"] + ([d["total"]] if d["classes"] else [])
        self.table_classes.setRowCount(len(lignes))
        for i, c in enumerate(lignes):
            gras = c is d["total"]
            valeurs = [c["classe"], c["eleves"], fcfa(c["net"]), fcfa(c["paye"]),
                       fcfa(c["reste"]), None,
                       fcfa(c["retard"]) if c["suivi"] else "-",
                       c["en_retard"] if c["suivi"] else "-"]
            for col, valeur in enumerate(valeurs):
                if col == 5:
                    if c["taux"] is None:
                        self.table_classes.setItem(i, col, self._item("-"))
                    else:
                        self.table_classes.setCellWidget(i, col, _barre(c["taux"]))
                else:
                    self.table_classes.setItem(
                        i, col, self._item(valeur, droite=col > 0, gras=gras))

    def _remplir_mois(self, d):
        self.table_mois.setRowCount(len(d["mois"]))
        for i, m in enumerate(d["mois"]):
            libelle = m["libelle"] + (" (en cours)" if m["en_cours"] else "")
            self.table_mois.setItem(i, 0, self._item(libelle))
            self.table_mois.setItem(i, 1, self._item(
                "-" if m["a_venir"] else fcfa(m["encaisse"]), droite=True))
            self.table_mois.setItem(i, 2, self._item(fcfa(m["prevu"]), droite=True))
            if m["a_venir"]:
                self.table_mois.setItem(i, 3, self._item("à venir", couleur="gris"))
            elif m["taux"] is None:
                self.table_mois.setItem(i, 3, self._item("-"))
            else:
                self.table_mois.setCellWidget(i, 3, _barre(m["taux"]))
            self.table_mois.setItem(i, 4, self._item(
                "-" if m["a_venir"] else fcfa(m["cumul_encaisse"]), droite=True))
            self.table_mois.setItem(i, 5, self._item(fcfa(m["cumul_prevu"]), droite=True))

    def _exporter(self):
        if self.donnees is None or not self.donnees["classes"]:
            QMessageBox.information(self, "Recouvrement", "Rien à exporter pour cette année.")
            return
        try:
            chemin = exporter_recouvrement(self.donnees, self.dossier_exports)
        except OSError as e:
            QMessageBox.warning(self, "Export impossible", str(e))
            return
        apres_export(self, chemin)