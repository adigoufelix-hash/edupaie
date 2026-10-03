from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

COULEURS_STATUT = {
    "Soldé": ("#dcfce7", "#166534"),
    "Partiellement payé": ("#ffedd5", "#9a3412"),
    "Non payé": ("#fee2e2", "#991b1b"),
}


def pastille(texte, fond, encre):
    label = QLabel(texte)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{fond}; color:{encre}; border-radius:10px;"
        "padding:3px 10px; font-weight:600; font-size:12px;")
    return label


def cellule_pastille(statut):
    """Pastille de statut centrée dans une cellule de tableau."""
    fond, encre = COULEURS_STATUT[statut]
    conteneur = QWidget()
    ligne = QHBoxLayout(conteneur)
    ligne.setContentsMargins(8, 4, 8, 4)
    ligne.addWidget(pastille(statut, fond, encre))
    ligne.addStretch()
    return conteneur


def avatar(nom, prenom):
    label = QLabel((nom[:1] + prenom[:1]).upper())
    label.setFixedSize(36, 36)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        "background:#4f46e5; color:white; border-radius:18px; font-weight:bold;")
    return label


class CarteKpi(QFrame):
    def __init__(self, icone, titre, fond_icone):
        super().__init__()
        self.setObjectName("carte")
        pastille_icone = QLabel(icone)
        pastille_icone.setFixedSize(46, 46)
        pastille_icone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pastille_icone.setStyleSheet(
            f"background:{fond_icone}; border-radius:23px; font-size:18px;")
        self.titre = QLabel(titre)
        self.titre.setObjectName("titreCarte")
        self.valeur = QLabel("0")
        self.valeur.setObjectName("valeurCarte")
        self.detail = QLabel("")
        self.detail.setObjectName("sousCarte")
        texte = QVBoxLayout()
        texte.setSpacing(2)
        for widget in (self.titre, self.valeur, self.detail):
            texte.addWidget(widget)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(16, 14, 16, 14)
        ligne.setSpacing(14)
        ligne.addWidget(pastille_icone)
        ligne.addLayout(texte, 1)

    def maj(self, valeur, detail=""):
        self.valeur.setText(valeur)
        self.detail.setText(detail)


class AnneauProgression(QWidget):
    """Anneau de pourcentage dessiné avec QPainter."""

    def __init__(self):
        super().__init__()
        self.pourcentage = 0.0
        self.setMinimumSize(190, 190)

    def definir(self, pourcentage):
        self.pourcentage = max(0.0, min(100.0, pourcentage))
        self.update()

    def paintEvent(self, event):
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        cote = min(self.width(), self.height()) - 28
        zone = QRectF((self.width() - cote) / 2, (self.height() - cote) / 2, cote, cote)
        stylo = QPen(QColor("#e5e7eb"), 14)
        stylo.setCapStyle(Qt.PenCapStyle.RoundCap)
        peintre.setPen(stylo)
        peintre.drawArc(zone, 0, 360 * 16)
        stylo.setColor(QColor("#4f46e5"))
        peintre.setPen(stylo)
        peintre.drawArc(zone, 90 * 16, int(-self.pourcentage / 100 * 360 * 16))
        peintre.setPen(QColor("#1e1b4b"))
        peintre.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        peintre.drawText(zone, Qt.AlignmentFlag.AlignCenter, f"{self.pourcentage:.0f} %")
        peintre.end()