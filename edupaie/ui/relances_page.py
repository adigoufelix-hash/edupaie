from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table


def _derniere(jours):
    if jours is None:
        return "jamais"
    if jours == 0:
        return "aujourd'hui"
    if jours == 1:
        return "hier"
    return f"il y a {jours} jours"


def _eleves(enfants):
    noms = [f"{e['nom']} ({e['classe']})" for e in enfants]
    texte = ", ".join(noms[:3])
    return texte + (f" et {len(noms) - 3} autre(s)" if len(noms) > 3 else "")


class RelancesPage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.destinataires = []
        self.donnees = None
        self._explique = False

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
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Parent / tuteur", "Élève(s)", "En retard", "Téléphone", "Dernière relance"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)
        self.progres = QLabel()

        tout = QPushButton("Tout cocher")
        rien = QPushButton("Tout décocher")
        suivant = QPushButton("Relancer le suivant")
        ligne = QPushButton("Relancer la ligne sélectionnée")
        sans = QPushButton("Élèves sans numéro...")
        tout.clicked.connect(lambda: self._cocher(Qt.CheckState.Checked))
        rien.clicked.connect(lambda: self._cocher(Qt.CheckState.Unchecked))
        suivant.clicked.connect(self._suivant)
        ligne.clicked.connect(self._ligne_selectionnee)
        sans.clicked.connect(self._sans_numero)

        haut = QHBoxLayout()
        haut.addWidget(QLabel("En retard au"))
        haut.addWidget(self.date)
        haut.addWidget(self.classe, 1)
        bas = QHBoxLayout()
        for bouton in (tout, rien, suivant, ligne, sans):
            bas.addWidget(bouton)
        bas.addStretch()
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.progres)
        mise_en_page.addLayout(bas)

        self.date.dateChanged.connect(self.recharger)
        self.classe.currentIndexChanged.connect(self.recharger)
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()  # les paiements ont pu changer entre-temps

    def _iso(self) -> str:
        return self.date.date().toString(Qt.DateFormat.ISODate)

    def recharger(self, *_):
        try:
            self.donnees = self.service.preparer(self._iso(), self.classe.currentData())
        except ErreurMetier as e:
            self.donnees, self.destinataires = None, []
            self.table.setRowCount(0)
            self.resume.setText(f"<span style='color:#991b1b'>{e}</span>")
            self.progres.setText("")
            return
        d = self.donnees
        self.destinataires = d["destinataires"]
        if d["nb_eleves"]:
            texte = (f"<b>{len(self.destinataires)}</b> parent(s) à relancer "
                     f"({d['nb_eleves']} élève(s), {fcfa(d['total_retard'])} en retard).")
        else:
            texte = "Aucun élève en retard à cette date."
        if d["sans_numero"]:
            texte += (f"<br><span style='color:#9a3412'>{len(d['sans_numero'])} élève(s) sans "
                      "numéro valide : renseigne leur contact pour pouvoir les relancer."
                      "</span>")
        if d["sans_echeancier"]:
            texte += (f"<br>{d['sans_echeancier']} élève(s) sont dans des classes sans "
                      "échéancier (non suivis).")
        self.resume.setText(texte)

        self.table.setRowCount(len(self.destinataires))
        for i, dest in enumerate(self.destinataires):
            valeurs = [dest["tuteur"] or "(parent non renseigné)", _eleves(dest["enfants"]),
                       fcfa(dest["retard"]), "+" + dest["telephone"],
                       _derniere(dest["jours_depuis"])]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if col == 0:  # la case à cocher est dans la première colonne
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Unchecked if dest["recente"]
                                       else Qt.CheckState.Checked)
                if col == 2:
                    item.setForeground(QColor("#991b1b"))
                if col == 4 and dest["recente"]:
                    item.setForeground(QColor("#6b7280"))
                self.table.setItem(i, col, item)
        self._maj_progres()

    def _cochees(self) -> list[int]:
        return [i for i in range(self.table.rowCount())
                if self.table.item(i, 0).checkState() == Qt.CheckState.Checked]

    def _cocher(self, etat):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(etat)
        self._maj_progres()

    def _maj_progres(self):
        n = len(self._cochees())
        self.progres.setText(f"{n} parent(s) coché(s) à relancer." if n else
                             "Aucun parent coché.")

    def _ouvrir(self, i: int, confirmer: bool) -> bool:
        dest = self.destinataires[i]
        if confirmer and dest["recente"]:
            if QMessageBox.question(
                    self, "Déjà relancé",
                    f"Ce parent a été relancé {_derniere(dest['jours_depuis'])}. "
                    "Le relancer quand même ?") != QMessageBox.StandardButton.Yes:
                return False
        try:
            resultat = self.service.lien_et_noter(
                self._iso(), self.classe.currentData(), dest["cle"])
        except ErreurMetier as e:
            QMessageBox.warning(self, "Relance impossible", str(e))
            return False
        QDesktopServices.openUrl(QUrl(resultat["lien"]))
        dest["recente"], dest["jours_depuis"] = True, 0
        self.table.item(i, 4).setText("aujourd'hui")
        self.table.item(i, 4).setForeground(QColor("#6b7280"))
        self.table.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
        self._maj_progres()
        return True

    def _suivant(self):
        cochees = self._cochees()
        if not cochees:
            QMessageBox.information(
                self, "Relances", "Aucun parent coché : coche ceux que tu veux relancer.")
            return
        if not self._explique:
            QMessageBox.information(
                self, "Comment ça marche",
                "WhatsApp va s'ouvrir avec le message déjà écrit pour ce parent.\n\n"
                "Appuie sur Envoyer dans WhatsApp, puis reviens ici et clique de nouveau sur "
                "« Relancer le suivant ».\n\nEduPaie note que la conversation a été ouverte, pas "
                "que le message est parti.")
            self._explique = True
        self._ouvrir(cochees[0], confirmer=False)

    def _ligne_selectionnee(self):
        i = self.table.currentRow()
        if i < 0:
            QMessageBox.information(self, "Relances", "Sélectionne d'abord un parent.")
            return
        self._ouvrir(i, confirmer=True)

    def _sans_numero(self):
        if self.donnees is None or not self.donnees["sans_numero"]:
            QMessageBox.information(self, "Relances",
                                    "Tous les élèves en retard ont un numéro valide.")
            return
        liste = self.donnees["sans_numero"]
        lignes = [f"- {e['nom']} ({e['classe']}) : {fcfa(e['retard'])}" for e in liste[:20]]
        if len(liste) > 20:
            lignes.append(f"... et {len(liste) - 20} autre(s)")
        QMessageBox.information(
            self, "Élèves sans numéro valide",
            "Renseigne le contact de ces élèves (fiche de l'élève, bouton « Contact du "
            "parent ») :\n\n" + "\n".join(lignes))