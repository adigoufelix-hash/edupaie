from PySide6.QtCore import QEvent, QObject, QTimer


class DetecteurInactivite(QObject):
    """Appelle `action` si aucune activité (souris, clavier) pendant `delai_ms`."""

    EVENEMENTS = (
        QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
        QEvent.Type.KeyPress, QEvent.Type.Wheel,
    )

    def __init__(self, delai_ms, action, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delai_ms)
        self.timer.timeout.connect(action)
        self.timer.start()

    def eventFilter(self, obj, event):
        if event.type() in self.EVENEMENTS:
            self.timer.start()  # relance le compte à rebours
        return False

    def arreter(self):
        self.timer.stop()