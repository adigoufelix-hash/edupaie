from PySide6.QtWidgets import QApplication

from edupaie.services import couleurs
from edupaie.ui.style import STYLE


def style_pour(couleur: str) -> str:
    """Feuille de style d'origine recolorée avec la couleur de l'école."""
    return couleurs.appliquer_a_style(STYLE, couleur)


def appliquer(couleur: str) -> None:
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(style_pour(couleur))