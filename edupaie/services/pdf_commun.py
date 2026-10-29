from io import BytesIO

from PIL import Image


def l1(texte) -> str:
    """Helvetica ne gère que le latin-1 : on évite un plantage sur un caractère exotique."""
    return str(texte or "").encode("latin-1", "replace").decode("latin-1")


def adapter(pdf, texte, largeur, taille_max, taille_min=8, style="B"):
    """Réduit la police puis coupe le texte (« ... ») pour qu'il tienne dans `largeur` mm.
    Retourne (texte, taille)."""
    texte = l1(texte)
    taille = taille_max
    pdf.set_font("Helvetica", style, taille)
    while taille > taille_min and pdf.get_string_width(texte) > largeur:
        taille -= 0.5
        pdf.set_font("Helvetica", style, taille)
    base = texte
    while len(base) > 1 and pdf.get_string_width(texte) > largeur:
        base = base[:-1]
        texte = base.rstrip() + "..."
    return texte, taille


def dessiner_logo(pdf, logo, x, y, cote) -> bool:
    """Dessine le logo dans un carré blanc de `cote` mm. False s'il est absent ou illisible."""
    if not logo:
        return False
    try:
        largeur, hauteur = Image.open(BytesIO(logo)).size
    except Exception:
        return False
    marge = 1.2
    zone = cote - 2 * marge
    if largeur >= hauteur:
        w, h = zone, zone * hauteur / largeur
    else:
        w, h = zone * largeur / hauteur, zone
    try:
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x, y, cote, cote, style="F", round_corners=True, corner_radius=2)
        pdf.image(BytesIO(logo), x=x + marge + (zone - w) / 2,
                  y=y + marge + (zone - h) / 2, w=w, h=h)
    except Exception:
        return False
    return True


def dessiner_qr(pdf, contenu, x, y, cote) -> bool:
    """Dessine un QR code dans un carré blanc de `cote` mm. False si impossible."""
    try:
        import segno
        matrice = segno.make(contenu, error="m", micro=False).matrix
    except Exception:
        return False
    taille = len(matrice)
    marge = 2  # zone calme, en modules
    module = cote / (taille + 2 * marge)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, cote, cote, style="F")
    pdf.set_fill_color(0, 0, 0)
    for j, ligne in enumerate(matrice):
        for i, sombre in enumerate(ligne):
            if sombre:  # léger recouvrement pour éviter les fines lignes blanches
                pdf.rect(x + (i + marge) * module, y + (j + marge) * module,
                         module + 0.02, module + 0.02, style="F")
    return True