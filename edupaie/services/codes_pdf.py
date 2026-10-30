import textwrap
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from edupaie.services.ecole import courant
from edupaie.services.pdf_commun import adapter, dessiner_logo, l1

CONSIGNES = [
    "Chaque code permet de créer un nouveau mot de passe pour ce compte, une seule fois.",
    "À utiliser depuis l'écran de connexion : « Mot de passe oublié ? ».",
    "Conserve cette feuille dans un endroit sûr et fermé (coffre, armoire), jamais à côté "
    "de l'ordinateur.",
    "Quiconque possède un de ces codes peut prendre le contrôle du compte administrateur.",
    "Après l'impression, supprime le fichier PDF de l'ordinateur.",
]


def generer_codes_pdf(codes, nom_utilisateur, dossier, ecole=None) -> Path:
    """Feuille de codes de secours à imprimer (format A5)."""
    ecole = ecole or courant()
    pdf = FPDF(unit="mm", format=(148, 210))
    pdf.set_auto_page_break(False)
    pdf.add_page()

    pdf.set_fill_color(*ecole.couleur_sombre)
    pdf.rect(0, 0, 148, 34, style="F")
    x = 38 if dessiner_logo(pdf, ecole.logo, 12, 6, 22) else 12
    nom, taille = adapter(pdf, ecole.nom_affiche, 136 - x, 18, 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", taille)
    pdf.set_xy(x, 8)
    pdf.cell(136 - x, 9, nom)
    titre, taille = adapter(pdf, "CODES DE SECOURS - ADMINISTRATEUR", 136 - x, 10, 7, style="")
    pdf.set_text_color(199, 210, 254)
    pdf.set_font("Helvetica", "", taille)
    pdf.set_xy(x, 20)
    pdf.cell(136 - x, 6, titre)

    compte, taille = adapter(pdf, f"Compte : {nom_utilisateur}", 124, 11, 7)
    pdf.set_text_color(30, 27, 75)
    pdf.set_font("Helvetica", "B", taille)
    pdf.set_xy(12, 44)
    pdf.cell(124, 6, compte)
    pdf.set_text_color(107, 114, 128)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(12, 51)
    pdf.cell(124, 5, l1(f"Feuille éditée le {datetime.now():%d/%m/%Y à %H:%M}"))

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Courier", "B", 15)
    for i, code in enumerate(codes):
        colonne, ligne = divmod(i, 4)
        pdf.set_xy(14 + colonne * 62, 64 + ligne * 11)
        pdf.cell(60, 8, f"{i + 1}. {code}")

    pdf.set_text_color(55, 65, 81)
    pdf.set_font("Helvetica", "", 9)
    y = 116.0
    for consigne in CONSIGNES:
        for k, morceau in enumerate(textwrap.wrap(consigne, 68)):
            pdf.set_xy(12, y)
            pdf.cell(124, 5, l1(("- " if k == 0 else "  ") + morceau))
            y += 5
        y += 1.5

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"codes_secours_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
    pdf.output(str(chemin))
    return chemin