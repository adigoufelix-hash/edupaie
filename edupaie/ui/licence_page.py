from html import escape
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from edupaie.services.ecole import courant
from edupaie.services.licence import SUPPORT_EMAIL, SUPPORT_WHATSAPP
from edupaie.services.paiement_service import ErreurMetier
from edupaie.version import VERSION

STYLES = {"licence": ("#dcfce7", "#166534"), "essai": ("#ffedd5", "#9a3412"),
          "expire": ("#fee2e2", "#991b1b")}


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


class ActivationDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.etat = None
        self.setWindowTitle("Activer une licence")
        self.resize(580, 380)
        aide = QLabel("Colle ici la clé de licence reçue de ton fournisseur (elle "
                      "commence par EDUPAIE1), ou charge le fichier .licence qui t'a "
                      "été envoyé.")
        aide.setWordWrap(True)
        self.cle = QPlainTextEdit()
        self.cle.setPlaceholderText("EDUPAIE1.eyJ2IjoxLC...")
        charger = QPushButton("Charger un fichier de licence...")
        activer = QPushButton("Activer")
        annuler = QPushButton("Annuler")
        charger.clicked.connect(self._charger)
        activer.clicked.connect(self._activer)
        annuler.clicked.connect(self.reject)
        bas = QHBoxLayout()
        bas.addWidget(charger)
        bas.addStretch()
        bas.addWidget(activer)
        bas.addWidget(annuler)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(aide)
        mise_en_page.addWidget(self.cle, 1)
        mise_en_page.addLayout(bas)

    def _charger(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Fichier de licence", "", "Licence EduPaie (*.licence *.txt)")
        if not chemin:
            return
        try:
            self.cle.setPlainText(Path(chemin).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            QMessageBox.warning(self, "Fichier illisible",
                                "Ce fichier n'est pas un fichier de licence EduPaie.")

    def _activer(self):
        try:
            self.etat = self.service.activer(self.cle.toPlainText())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Licence refusée", str(e))
            return
        self.accept()


class LicencePage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        titre = QLabel("<h3 style='margin:0'>Licence</h3>")
        self.resume = QLabel()
        self.resume.setWordWrap(True)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setWordWrap(True)

        self.machine = QLineEdit(service.machine())
        self.machine.setReadOnly(True)
        copier = QPushButton("Copier")
        copier.clicked.connect(self._copier)
        demander = QPushButton("Demander une licence")
        activer = QPushButton("Activer une licence...")
        demander.clicked.connect(self._demander)
        activer.clicked.connect(self._activer)

        ligne = QHBoxLayout()
        ligne.addWidget(self.machine, 1)
        ligne.addWidget(copier)
        boutons = QHBoxLayout()
        boutons.addWidget(demander)
        boutons.addWidget(activer)
        boutons.addStretch()
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(titre)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addWidget(self.details)
        mise_en_page.addSpacing(10)
        mise_en_page.addWidget(QLabel("Identifiant de cet ordinateur (à communiquer à ton "
                                      "fournisseur) :"))
        mise_en_page.addLayout(ligne)
        mise_en_page.addLayout(boutons)
        mise_en_page.addStretch()
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()

    def recharger(self):
        etat = self.service.etat()
        fond, encre = STYLES[etat.mode]
        self.resume.setText(etat.message)
        self.resume.setStyleSheet(
            f"background: {fond}; color: {encre}; border-radius: 10px; padding: 14px; "
            "font-weight: bold;")
        lignes = []
        if etat.licence_id:
            lignes.append(f"Licence n° <b>{escape(etat.licence_id)}</b>")
        if etat.ecole:
            lignes.append(f"École : <b>{escape(etat.ecole)}</b>")
        if etat.mode == "licence":
            lignes.append("Valable jusqu'au : <b>" + (
                _date_fr(etat.expire_le) if etat.expire_le else "sans limite de durée")
                + "</b>")
        if etat.avertissement:
            lignes.append(f"<span style='color:#9a3412'>{escape(etat.avertissement)}</span>")
        if not self.service.configuree():
            lignes.append("<span style='color:#991b1b'>⚠ Développeur : la clé publique "
                          "n'est pas configurée (outils/generer_cles.py).</span>")
            lignes.append(f"Version d'EduPaie : <b>{VERSION}</b>")
        self.details.setText("<br>".join(lignes))

    def _copier(self):
        QApplication.clipboard().setText(self.machine.text())
        QMessageBox.information(self, "Copié", "Identifiant copié dans le presse-papiers.")

    def _demander(self):
        ecole = courant().nom or "mon école"
        texte = (f"Bonjour, je souhaite activer EduPaie pour l'école « {ecole} ».\n"
                 f"Identifiant de mon ordinateur : {self.service.machine()}")
        if SUPPORT_WHATSAPP:
            QDesktopServices.openUrl(QUrl(f"https://wa.me/{SUPPORT_WHATSAPP}?text={quote(texte)}"))
            return
        QApplication.clipboard().setText(texte)
        suite = f"\nEnvoie-le à : {SUPPORT_EMAIL}" if SUPPORT_EMAIL else ""
        QMessageBox.information(
            self, "Demande de licence",
            "Le message est copié : colle-le dans WhatsApp ou dans un e-mail à ton "
            f"fournisseur.{suite}\n\n{texte}")

    def _activer(self):
        dialogue = ActivationDialog(self.service, self)
        if dialogue.exec() != QDialog.Accepted:
            return
        QMessageBox.information(
            self, "Licence activée",
            f"{dialogue.etat.message}\n\nL'application se rouvre pour appliquer la "
            "licence : reconnecte-toi.")
        self.window().deconnecter()