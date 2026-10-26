from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QPushButton

# Marge intérieure du style (2 x 18 px) + bordures, avec une petite réserve
MARGE_HORIZONTALE = 44


class ProtegeBoutons(QObject):
    """Empêche qu'un bouton soit plus étroit que son texte (texte coupé)."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Polish and isinstance(obj, QPushButton):
            self._ajuster(obj)
        return False

    @staticmethod
    def _ajuster(bouton):
        texte = bouton.text().replace("&", "")
        if not texte:
            return
        police = QFont(bouton.font())
        police.setBold(True)  # cas le plus large : le style met les boutons en gras
        largeur = QFontMetrics(police).horizontalAdvance(texte) + MARGE_HORIZONTALE
        if bouton.minimumWidth() < largeur:
            bouton.setMinimumWidth(largeur)