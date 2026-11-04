"""Crée assets/EduPaie.ico (à lancer une fois) : python -m outils.creer_icone"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TAILLES = [16, 24, 32, 48, 64, 128, 256]


def dessiner(taille=256):
    image = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    dessin.rounded_rectangle((0, 0, taille - 1, taille - 1), radius=taille // 5,
                             fill=(79, 70, 229, 255))
    try:
        police = ImageFont.truetype("arialbd.ttf", int(taille * 0.5))
    except OSError:
        police = ImageFont.load_default(int(taille * 0.5))
    dessin.text((taille / 2, taille / 2), "EP", font=police, fill="white", anchor="mm")
    return image


def main():
    dossier = Path(__file__).resolve().parent.parent / "assets"
    dossier.mkdir(exist_ok=True)
    chemin = dossier / "EduPaie.ico"
    dessiner().save(chemin, format="ICO", sizes=[(t, t) for t in TAILLES])
    print("Icône créée :", chemin)


if __name__ == "__main__":
    main()