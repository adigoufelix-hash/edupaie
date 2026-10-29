from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.style import preparer_table


class AjoutClassesDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Ajouter des classes")
        self.resize(560, 480)

        aide = QLabel(
            "Écris une classe par ligne, ou génère une série : le niveau <b>6e</b> avec "
            "les sections <b>A B C D</b> donne 6e A, 6e B, 6e C et 6e D.")
        aide.setWordWrap(True)
        self.niveau = QLineEdit()
        self.niveau.setPlaceholderText("Niveau, ex. : 6e")
        self.sections = QLineEdit()
        self.sections.setPlaceholderText("Sections, ex. : A B C D (vide = sans section)")
        generer = QPushButton("Générer la série")
        generer.clicked.connect(self._generer)
        self.texte = QPlainTextEdit()
        self.texte.setPlaceholderText("6e A\n6e B\n5e A\n...")
        ajouter = QPushButton("Ajouter ces classes")
        annuler = QPushButton("Annuler")
        ajouter.clicked.connect(self._ajouter)
        annuler.clicked.connect(self.reject)

        serie = QHBoxLayout()
        serie.addWidget(self.niveau, 1)
        serie.addWidget(self.sections, 2)
        serie.addWidget(generer)
        bas = QHBoxLayout()
        bas.addStretch()
        bas.addWidget(ajouter)
        bas.addWidget(annuler)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(serie)
        mise_en_page.addWidget(self.texte, 1)
        mise_en_page.addLayout(bas)

    def _generer(self):
        try:
            noms = self.service.serie(self.niveau.text(), self.sections.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Série impossible", str(e))
            return
        self.texte.appendPlainText("\n".join(noms))
        self.sections.clear()
        self.niveau.setFocus()

    def _ajouter(self):
        try:
            ajoutees, ignorees = self.service.ajouter_plusieurs(
                self.texte.toPlainText().splitlines())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Données invalides", str(e))
            return
        message = f"{ajoutees} classe(s) ajoutée(s)."
        if ignorees:
            message += f" {ignorees} existaient déjà."
        QMessageBox.information(self, "Classes", message)
        self.accept()


class ClassesPage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        titre = QLabel("<h3 style='margin:0'>Classes de l'école</h3>")
        aide = QLabel(
            "Ces classes apparaissent dans les listes de choix (nouvel élève, frais, "
            "échéancier). L'ordre choisi ici est celui des listes.")
        aide.setWordWrap(True)
        self.resume = QLabel()

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Classe", "Élèves", "Lignes de frais", "Tranches"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        ajouter = QPushButton("Ajouter des classes...")
        renommer = QPushButton("Renommer")
        supprimer = QPushButton("Supprimer")
        supprimer.setObjectName("danger")
        monter = QPushButton("▲ Monter")
        descendre = QPushButton("▼ Descendre")
        ajouter.clicked.connect(self._ajouter)
        renommer.clicked.connect(self._renommer)
        supprimer.clicked.connect(self._supprimer)
        monter.clicked.connect(lambda: self._deplacer(-1))
        descendre.clicked.connect(lambda: self._deplacer(1))

        bas = QHBoxLayout()
        for bouton in (ajouter, renommer, supprimer, monter, descendre):
            bas.addWidget(bouton)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(titre)
        mise_en_page.addWidget(aide)
        mise_en_page.addWidget(self.table)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addLayout(bas)
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()

    def recharger(self, garder=None):
        lignes = self.service.lister()
        self.table.setRowCount(len(lignes))
        cible = -1
        for i, ligne in enumerate(lignes):
            valeurs = (ligne["nom"], str(ligne["eleves"]), str(ligne["frais"]),
                       str(ligne["tranches"]))
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, col, item)
            if garder and ligne["nom"].casefold() == garder.casefold():
                cible = i
        if cible >= 0:
            self.table.selectRow(cible)
        self.resume.setText(f"{len(lignes)} classe(s)")

    def _nom(self):
        i = self.table.currentRow()
        if i < 0:
            QMessageBox.information(self, "Sélection", "Sélectionne d'abord une classe.")
            return None
        return self.table.item(i, 0).text()

    def _ajouter(self):
        if AjoutClassesDialog(self.service, self).exec() == QDialog.Accepted:
            self.recharger()

    def _renommer(self):
        nom = self._nom()
        if nom is None:
            return
        nouveau, ok = QInputDialog.getText(
            self, "Renommer la classe",
            f"Nouveau nom pour « {nom} » (il est aussi changé chez les élèves, "
            "dans les frais et dans l'échéancier) :", QLineEdit.Normal, nom)
        if not ok:
            return
        try:
            self.service.renommer(nom, nouveau)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Renommage impossible", str(e))
            return
        self.recharger(garder=nouveau)

    def _supprimer(self):
        nom = self._nom()
        if nom is None:
            return
        if QMessageBox.question(self, "Confirmation",
                                f"Supprimer la classe « {nom} » ?") != QMessageBox.Yes:
            return
        try:
            self.service.supprimer(nom)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Suppression impossible", str(e))
            return
        self.recharger()

    def _deplacer(self, delta):
        nom = self._nom()
        if nom is None:
            return
        try:
            self.service.deplacer(nom, delta)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Déplacement impossible", str(e))
            return
        self.recharger(garder=nom)