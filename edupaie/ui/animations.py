from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import QDialog, QGraphicsOpacityEffect

ANIMATIONS_ACTIVES = True  # mettre False pour tout désactiver
DUREE_MS = 180


class FonduDialogues(QObject):
    """Fait apparaître chaque fenêtre de dialogue en fondu."""

    def eventFilter(self, obj, event):
        if ANIMATIONS_ACTIVES and isinstance(obj, QDialog):
            if event.type() == QEvent.Type.Polish:
                obj.setWindowOpacity(0.0)
            elif event.type() == QEvent.Type.Show and obj.windowOpacity() < 1.0:
                animation = QPropertyAnimation(obj, b"windowOpacity", obj)
                animation.setDuration(DUREE_MS)
                animation.setStartValue(0.0)
                animation.setEndValue(1.0)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        return False


def fondu_page(widget):
    """Fait apparaître une page en fondu (l'effet est retiré à la fin)."""
    if not ANIMATIONS_ACTIVES or widget is None:
        return
    effet = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effet)
    animation = QPropertyAnimation(effet, b"opacity", widget)
    animation.setDuration(DUREE_MS)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)