from PySide6.QtCore import QMarginsF, Qt, QUrl
from PySide6.QtGui import (QDesktopServices, QFont, QPageLayout, QPageSize,
                           QTextDocument)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

from edupaie.services import couleurs
from edupaie.services.ecole import courant
from edupaie.services.guide import ECRANS


class GuidePage(QWidget):
    def __init__(self, service, demarrage=None, aller_a=None):
        super().__init__()
        self.service = service
        self.demarrage = demarrage
        self.aller_a = aller_a  # fonction(titre d'écran) -> True si l'écran existe
        self.courant = None

        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("Rechercher dans le guide (ex. : annuler un paiement)")
        self.resume = QLabel()
        self.liste = QListWidget()
        self.liste.setFixedWidth(320)
        self.lecteur = QTextBrowser()
        self.lecteur.setOpenLinks(False)
        pdf = QPushButton("Enregistrer le guide en PDF")

        gauche = QVBoxLayout()
        gauche.addWidget(self.recherche)
        gauche.addWidget(self.resume)
        gauche.addWidget(self.liste, 1)
        gauche.addWidget(pdf)
        mise_en_page = QHBoxLayout(self)
        mise_en_page.addLayout(gauche)
        mise_en_page.addWidget(self.lecteur, 1)

        self.recherche.textChanged.connect(self._remplir)
        self.liste.currentItemChanged.connect(self._selection)
        self.lecteur.anchorClicked.connect(self._lien)
        pdf.clicked.connect(self._pdf)
        self._remplir()

    def showEvent(self, event):
        super().showEvent(event)
        if self.courant == "demarrage":  # les étapes ont pu changer entre-temps
            self._afficher("demarrage")

    @staticmethod
    def _couleur() -> str:
        return "#%02x%02x%02x" % couleurs.principale_rgb(courant().couleur)

    # --- Liste ------------------------------------------------------------------------------
    def _ajouter(self, identifiant, titre):
        item = QListWidgetItem(titre)
        item.setData(Qt.ItemDataRole.UserRole, identifiant)
        self.liste.addItem(item)

    def _trouver(self, identifiant):
        for i in range(self.liste.count()):
            item = self.liste.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == identifiant:
                return item
        return None

    def _remplir(self, *_):
        texte = self.recherche.text().strip()
        self.liste.blockSignals(True)
        self.liste.clear()
        if texte:
            resultats = self.service.rechercher(texte)
            for article in resultats:
                self._ajouter(article.id, article.titre)
            self.resume.setText(f"{len(resultats)} résultat(s)")
        else:
            self.resume.setText("")
            if self.demarrage is not None and self.demarrage.visible():
                self._ajouter("demarrage", "★ Pour bien démarrer")
            for categorie, articles in self.service.par_categorie():
                entete = QListWidgetItem(categorie.upper())
                police = entete.font()
                police.setBold(True)
                entete.setFont(police)
                entete.setFlags(Qt.ItemFlag.NoItemFlags)  # simple intitulé, non sélectionnable
                self.liste.addItem(entete)
                for article in articles:
                    self._ajouter(article.id, article.titre)
        self.liste.blockSignals(False)
        cible = self._trouver(self.courant)
        if cible is None:
            cible = next((self.liste.item(i) for i in range(self.liste.count())
                          if self.liste.item(i).data(Qt.ItemDataRole.UserRole)), None)
        if cible is not None:
            self.liste.setCurrentItem(cible)
        else:
            self.lecteur.setHtml("<p>Aucun résultat. Essaie d'autres mots.</p>")

    def _selection(self, item, _precedent=None):
        identifiant = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if identifiant:
            self.courant = identifiant
            self._afficher(identifiant)

    def _afficher(self, identifiant):
        couleur = self._couleur()
        if identifiant == "demarrage" and self.demarrage is not None:
            html = self.service.html_demarrage(self.demarrage.etapes(), couleur)
        else:
            article = self.service.article(identifiant)
            html = (self.service.html(article, couleur) if article
                    else "<p>Cette rubrique n'est pas disponible pour ton rôle.</p>")
        self.lecteur.setHtml(html)

    # --- Liens internes ------------------------------------------------------------------------
    def _lien(self, url):
        cible = url.toString()
        if cible.startswith("guide:"):
            identifiant = cible[len("guide:"):]
            if self.service.article(identifiant) is None:
                QMessageBox.information(self, "Guide",
                                        "Cette rubrique n'est pas disponible pour ton rôle.")
                return
            self.recherche.blockSignals(True)
            self.recherche.clear()
            self.recherche.blockSignals(False)
            self.courant = identifiant
            self._remplir()
        elif cible.startswith("ecran:"):
            titre = ECRANS.get(cible[len("ecran:"):])
            if titre and self.aller_a and not self.aller_a(titre):
                QMessageBox.information(
                    self, "Écran indisponible",
                    "Cet écran n'est pas disponible avec ton rôle ou l'état de ta licence.")

    # --- Export PDF ---------------------------------------------------------------------------------
    def _pdf(self):
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le guide", "Guide_EduPaie.pdf", "PDF (*.pdf)")
        if not chemin:
            return
        document = QTextDocument()
        document.setDefaultFont(QFont("Segoe UI", 10))
        document.setHtml(self.service.document(
            self.service.articles(), courant().nom, self._couleur()))
        imprimante = QPrinter(QPrinter.PrinterMode.HighResolution)
        imprimante.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        imprimante.setOutputFileName(chemin)
        imprimante.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        imprimante.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        document.print_(imprimante)
        QDesktopServices.openUrl(QUrl.fromLocalFile(chemin))