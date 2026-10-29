import colorsys
import re

BASE_PRINCIPALE = (79, 70, 229)  # #4F46E5 : couleur d'origine d'EduPaie
MARINE = (30, 27, 75)            # couleur sombre d'origine (menu latéral)
BLANC = (255, 255, 255)

TEINTE_MIN, TEINTE_MAX = 224, 270  # famille « indigo » du style, en degrés
SATURATION_MIN = 0.25
CONTRASTE_MIN = 4.5                # lisibilité du texte blanc sur la couleur principale

_HEX6 = re.compile(r"#[0-9a-fA-F]{6}\b")
_RGB = re.compile(
    r"rgb(a?)\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*((?:,\s*[\d.]+\s*)?)\)")


def normaliser(texte):
    """'#0f766e' ou '0f766e' -> '#0F766E' ; None si invalide."""
    brut = str(texte or "").strip().lstrip("#")
    return "#" + brut.upper() if re.fullmatch(r"[0-9a-fA-F]{6}", brut) else None


def _en_rgb(code):
    return tuple(int(code[i:i + 2], 16) for i in (1, 3, 5))


def _en_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _hls(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))


def _depuis_hls(h, l, s):
    return tuple(max(0, min(255, round(c * 255))) for c in colorsys.hls_to_rgb(h, l, s))


def _lineaire(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_lineaire(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(rgb1, rgb2):
    clair, sombre = sorted((luminance(rgb1), luminance(rgb2)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


def ajuster_principale(couleur):
    """(code, modifiée) : assombrit la couleur si le texte blanc serait illisible dessus.
    (None, False) si la couleur est invalide."""
    code = normaliser(couleur)
    if code is None:
        return None, False
    rgb = _en_rgb(code)
    if contraste(rgb, BLANC) >= CONTRASTE_MIN:
        return code, False
    h, l, s = _hls(rgb)
    candidat = rgb
    while l > 0.05:
        l -= 0.01
        candidat = _depuis_hls(h, l, s)
        if contraste(candidat, BLANC) >= CONTRASTE_MIN:
            break
    return _en_hex(candidat), True


_H0, _L0, _S0 = _hls(BASE_PRINCIPALE)


def _cible(couleur):
    """Couleur principale effective en (teinte, clarté, saturation), ou None si rien à changer."""
    ajustee, _ = ajuster_principale(couleur)
    if ajustee is None:
        return None
    rgb = _en_rgb(ajustee)
    return None if rgb == BASE_PRINCIPALE else _hls(rgb)


def _transformer(rgb, cible):
    """Fait suivre à une couleur de la marque la nouvelle couleur principale.
    Les couleurs hors de la famille indigo (gris, rouge, vert...) ne changent pas."""
    if cible is None:
        return tuple(rgb)
    h, l, s = _hls(rgb)
    if not (TEINTE_MIN <= h * 360 <= TEINTE_MAX and s >= SATURATION_MIN):
        return tuple(rgb)
    ht, lt, st = cible
    h2 = (h + (ht - _H0)) % 1.0
    s2 = min(1.0, s * (st / _S0))
    poids = min(l, 1 - l) / min(_L0, 1 - _L0)  # les extrêmes (très clair/sombre) bougent peu
    l2 = min(1.0, max(0.0, l + (lt - _L0) * poids))
    return _depuis_hls(h2, l2, s2)


def theme_rgb(couleur, rgb):
    return _transformer(rgb, _cible(couleur))


def principale_rgb(couleur):
    ajustee, _ = ajuster_principale(couleur)
    return _en_rgb(ajustee) if ajustee else BASE_PRINCIPALE


def sombre_rgb(couleur):
    return theme_rgb(couleur, MARINE)


def appliquer_a_style(style: str, couleur) -> str:
    """Recolore la feuille de style de l'application avec la couleur de l'école."""
    cible = _cible(couleur)
    if cible is None:
        return style

    def en_hex(m):
        return _en_hex(_transformer(_en_rgb(m.group(0)), cible)).lower()

    def en_rgb(m):
        rgb = tuple(min(255, int(m.group(i))) for i in (2, 3, 4))
        r, g, b = _transformer(rgb, cible)
        return f"rgb{m.group(1)}({r}, {g}, {b}{m.group(5)})"

    return _RGB.sub(en_rgb, _HEX6.sub(en_hex, style))