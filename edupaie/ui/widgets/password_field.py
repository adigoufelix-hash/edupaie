from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLineEdit

_EYE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
)
_EYE_OFF = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94'
    'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19'
    'm-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>'
)


def _icon(svg: str, color: str = "#64748B") -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg.format(c=color).encode("utf-8")))
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return QIcon(pm)


class PasswordField(QLineEdit):
    """Champ mot de passe avec petit œil pour afficher / masquer."""

    def __init__(self, placeholder: str = "Mot de passe", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setEchoMode(QLineEdit.Password)
        self._icon_show = _icon(_EYE)
        self._icon_hide = _icon(_EYE_OFF)
        self._action = self.addAction(self._icon_show, QLineEdit.TrailingPosition)
        self._action.setToolTip("Afficher le mot de passe")
        self._action.triggered.connect(self._toggle)

    def _toggle(self):
        visible = self.echoMode() == QLineEdit.Password
        self.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._action.setIcon(self._icon_hide if visible else self._icon_show)
        self._action.setToolTip(
            "Masquer le mot de passe" if visible else "Afficher le mot de passe"
        )