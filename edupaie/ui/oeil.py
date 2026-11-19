"""L'œil qui affiche ou masque un mot de passe."""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLineEdit

from edupaie.ui.icones import icone_oeil

_setEchoMode_original = QLineEdit.setEchoMode


def ajouter_oeil(champ: QLineEdit) -> None:
    """Ajoute, à droite du champ, l'icône œil : un clic affiche le mot de passe, un autre le
    masque. Sans effet si le champ en a déjà un."""
    if getattr(champ, "_oeil_maj", None) is not None:
        return
    action = QAction(champ)

    def maj():
        visible = champ.echoMode() == QLineEdit.EchoMode.Normal
        action.setIcon(icone_oeil(barre=visible))
        action.setToolTip("Masquer le mot de passe" if visible else "Afficher le mot de passe")

    def basculer():
        visible = champ.echoMode() == QLineEdit.EchoMode.Normal
        _setEchoMode_original(champ, QLineEdit.EchoMode.Password if visible
                              else QLineEdit.EchoMode.Normal)
        maj()
        champ.setFocus()

    champ._oeil_maj = maj
    action.triggered.connect(basculer)
    champ.addAction(action, QLineEdit.ActionPosition.TrailingPosition)
    maj()


def installer_oeil() -> bool:
    """Tout champ réglé en mode « mot de passe » reçoit automatiquement l'œil, dans toutes les
    fenêtres de l'application. Retourne False si l'installation n'est pas possible."""
    if getattr(QLineEdit, "_oeil_installe", False):
        return True

    def setEchoMode(self, mode):
        _setEchoMode_original(self, mode)
        if mode == QLineEdit.EchoMode.Password:
            ajouter_oeil(self)
        elif getattr(self, "_oeil_maj", None) is not None:
            self._oeil_maj()

    try:
        QLineEdit.setEchoMode = setEchoMode
        QLineEdit._oeil_installe = True
    except (TypeError, AttributeError):
        return False
    return True
