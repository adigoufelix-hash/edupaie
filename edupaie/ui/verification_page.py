from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.paiement_dialog import MODES, fcfa

LIBELLES_MODES = {valeur: libelle for libelle, valeur in MODES}
STYLES = {
    "authentique": ("✔ REÇU AUTHENTIQUE", "#dcfce7", "#166534"),
    "annule": ("✖ REÇU ANNULÉ", "#fee2e2", "#991b1b"),
    "falsifie": ("✖ REÇU FALSIFIÉ OU MODIFIÉ", "#fee2e2", "#991b1b"),
    "introuvable": ("✖ REÇU INTROUVABLE", "#fee2e2", "#991b1b"),
    "non_controle": ("⚠ CODE NON VÉRIFIÉ", "#ffedd5", "#9a3412"),
    "invalide": ("Saisie illisible", "#e5e7eb", "#374151"),
}


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso[:10].split("-")
    return f"{jour}/{mois}/{annee}"


class VerificationPage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        titre = QLabel("<h3 style='margin:0'>Vérifier un reçu</h3>")
        aide = QLabel(
            "Place le curseur dans la case et scanne le QR code du reçu avec une "
            "douchette USB, ou tape le numéro du reçu suivi du code de contrôle "
            "(exemple : REC-2026-000001 A1B2C-3D4E5), puis appuie sur Entrée.")
        aide.setWordWrap(True)
        self.saisie = QLineEdit()
        self.saisie.setPlaceholderText("QR code ou numéro de reçu + code")
        verifier = QPushButton("Vérifier")
        self.saisie.returnPressed.connect(self._verifier)
        verifier.clicked.connect(self._verifier)

        self.bandeau = QLabel("En attente d'un reçu...")
        self.bandeau.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bandeau.setMinimumHeight(90)
        self.bandeau.setStyleSheet(
            "background: #f3f4f6; color: #6b7280; border-radius: 12px; "
            "font-size: 20px; font-weight: bold; padding: 16px;")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.RichText)

        ligne = QHBoxLayout()
        ligne.addWidget(self.saisie, 1)
        ligne.addWidget(verifier)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(titre)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(ligne)
        mise_en_page.addWidget(self.bandeau)
        mise_en_page.addWidget(self.message)
        mise_en_page.addWidget(self.details)
        mise_en_page.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        self.saisie.setFocus()

    def _verifier(self):
        try:
            resultat = self.service.verifier(self.saisie.text())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Vérification impossible", str(e))
            return
        texte, fond, encre = STYLES[resultat["statut"]]
        self.bandeau.setText(texte)
        self.bandeau.setStyleSheet(
            f"background: {fond}; color: {encre}; border-radius: 12px; "
            "font-size: 22px; font-weight: bold; padding: 16px;")
        self.message.setText(resultat["message"])
        self.details.setText(self._details(resultat["details"]))
        self.saisie.clear()  # prêt pour le reçu suivant
        self.saisie.setFocus()

    @staticmethod
    def _details(d):
        if not d:
            return ""
        lignes = [("Numéro", d["numero"]),
                  ("Élève", f"{d['eleve']} ({d['classe']})"),
                  ("Montant", fcfa(d["montant"])),
                  ("Date du paiement", _date_fr(d["date"])),
                  ("Mode", LIBELLES_MODES.get(d["mode"], d["mode"])),
                  ("Encaissé par", d["encaisse_par"] or "-")]
        if d["annule"]:
            lignes.append(("Annulation", f"le {_date_fr(d['annule_le'] or '0000-00-00')} par "
                           f"{d['annule_par'] or '-'} - motif : {d['motif_annulation'] or '-'}"))
        return ("<table cellpadding='4'>" + "".join(
            f"<tr><td><b>{escape(cle)}</b></td><td>{escape(str(valeur))}</td></tr>"
            for cle, valeur in lignes) + "</table>")