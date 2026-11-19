"""Petites icônes dessinées en code (pas de fichiers image à embarquer)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

GRIS = "#6b7280"
TAILLE = 64  # dessin en 64 px, réduit proprement par Qt


def _icone(dessiner, couleur=GRIS) -> QIcon:
    pix = QPixmap(TAILLE, TAILLE)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(couleur), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    dessiner(p, QColor(couleur))
    p.end()
    return QIcon(pix)


def icone_oeil(barre: bool = False, couleur: str = GRIS) -> QIcon:
    """Œil ouvert (le texte est masqué : cliquer l'affiche) ou œil barré (il est affiché)."""
    def dessiner(p, c):
        contour = QPainterPath()
        contour.moveTo(6, 32)
        contour.quadTo(32, 4, 58, 32)
        contour.quadTo(32, 60, 6, 32)
        p.drawPath(contour)
        p.setBrush(c)
        p.drawEllipse(QPointF(32, 32), 8, 8)
        if barre:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(c, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(12, 54), QPointF(52, 10))
    return _icone(dessiner, couleur)


def icone_utilisateur(couleur: str = GRIS) -> QIcon:
    def dessiner(p, c):
        p.drawEllipse(QPointF(32, 22), 11, 11)
        epaules = QPainterPath()
        epaules.moveTo(10, 56)
        epaules.cubicTo(10, 36, 54, 36, 54, 56)
        p.drawPath(epaules)
    return _icone(dessiner, couleur)


def icone_cadenas(couleur: str = GRIS) -> QIcon:
    def dessiner(p, c):
        p.drawRoundedRect(QRectF(12, 28, 40, 28), 6, 6)
        anse = QPainterPath()
        anse.moveTo(20, 28)
        anse.lineTo(20, 20)
        anse.arcTo(QRectF(20, 8, 24, 24), 180, -180)
        anse.lineTo(44, 28)
        p.drawPath(anse)
        p.setBrush(c)
        p.drawEllipse(QPointF(32, 42), 3, 3)
    return _icone(dessiner, couleur)
