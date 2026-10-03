from pathlib import Path

from fpdf import FPDF

MODES = {
    "especes": "Espèces",
    "cheque": "Chèque",
    "virement": "Virement",
    "mobile_money": "Mobile money",
}

MARINE = (30, 27, 75)
INDIGO = (79, 70, 229)
LAVANDE = (199, 210, 254)
CLAIR = (238, 242, 255)
BORDURE = (226, 232, 240)
GRIS = (107, 114, 128)
BLANC = (255, 255, 255)
VERT, FOND_VERT = (22, 101, 52), (220, 252, 231)
ORANGE, FOND_ORANGE = (154, 52, 18), (255, 237, 213)


def _montant(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ") + " FCFA"


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


def _texte(pdf, x, y, largeur, hauteur, contenu, taille,
           gras=False, couleur=MARINE, align="L"):
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B" if gras else "", taille)
    pdf.set_text_color(*couleur)
    pdf.cell(largeur, hauteur, contenu, align=align)


def _arrondi(pdf, x, y, largeur, hauteur, rayon, style):
    pdf.rect(x, y, largeur, hauteur, style=style,
             round_corners=True, corner_radius=rayon)


def generer_recu_pdf(eleve, paiement, dossier) -> Path:
    """Génère le reçu PDF à partir des seules données enregistrées."""
    pdf = FPDF(unit="mm", format=(148, 210))
    pdf.set_auto_page_break(False)
    pdf.add_page()

    # Bandeau d'en-tête
    pdf.set_fill_color(*MARINE)
    pdf.rect(0, 0, 148, 42, style="F")
    _texte(pdf, 12, 9, 70, 10, "EduPaie", 22, True, BLANC)
    _texte(pdf, 12, 20, 70, 5, "Gestion des paiements scolaires", 9, False, LAVANDE)
    _texte(pdf, 12, 31, 70, 6, "REÇU DE PAIEMENT", 11, True, BLANC)
    _texte(pdf, 70, 10, 66, 5, "N° DE REÇU", 8, False, LAVANDE, "R")
    _texte(pdf, 70, 16, 66, 8, paiement.numero_recu, 13, True, BLANC, "R")

    # Bloc élève
    pdf.set_draw_color(*BORDURE)
    pdf.set_fill_color(*CLAIR)
    _arrondi(pdf, 12, 50, 124, 30, 3, "DF")
    _texte(pdf, 18, 53, 112, 5, "ÉLÈVE", 8, True, INDIGO)
    _texte(pdf, 18, 59, 112, 8, f"{eleve.nom} {eleve.prenom}", 15, True)
    _texte(pdf, 18, 69, 112, 6,
           f"Classe {eleve.classe}  |  Année scolaire {eleve.annee_scolaire}",
           10, False, GRIS)

    # Date et mode de paiement
    pdf.set_fill_color(*BLANC)
    for x, titre, valeur in (
            (12, "DATE DU PAIEMENT", _date_fr(paiement.date_paiement)),
            (76, "MODE DE PAIEMENT", MODES.get(paiement.mode, paiement.mode))):
        _arrondi(pdf, x, 88, 60, 18, 3, "DF")
        _texte(pdf, x + 5, 91, 50, 4, titre, 7, True, GRIS)
        _texte(pdf, x + 5, 97, 50, 6, valeur, 12, True)

    # Montant payé
    pdf.set_fill_color(*INDIGO)
    _arrondi(pdf, 12, 114, 124, 28, 3, "F")
    _texte(pdf, 12, 119, 124, 5, "MONTANT PAYÉ", 8, True, LAVANDE, "C")
    _texte(pdf, 12, 126, 124, 12, _montant(paiement.montant), 24, True, BLANC, "C")

    # Récapitulatif
    total_verse = eleve.total_du - paiement.solde_apres
    lignes = (("Total des frais", _montant(eleve.total_du), False),
              ("Total versé à ce jour", _montant(total_verse), False),
              ("Solde restant", _montant(paiement.solde_apres), True))
    y = 150
    for libelle, valeur, fort in lignes:
        _texte(pdf, 12, y, 70, 8, libelle, 10, fort, MARINE if fort else GRIS)
        _texte(pdf, 82, y, 54, 8, valeur, 11, fort, MARINE, "R")
        pdf.set_draw_color(*BORDURE)
        pdf.line(12, y + 8, 136, y + 8)
        y += 9

    # Pastille de statut
    if paiement.solde_apres == 0:
        fond, encre, etiquette = FOND_VERT, VERT, "SOLDÉ"
    else:
        fond, encre, etiquette = FOND_ORANGE, ORANGE, "PAIEMENT PARTIEL"
    pdf.set_fill_color(*fond)
    _arrondi(pdf, 44, 182, 60, 9, 4.5, "F")
    _texte(pdf, 44, 184, 60, 5, etiquette, 9, True, encre, "C")

    _texte(pdf, 12, 197, 124, 5,
           "Merci de conserver ce reçu. Il fait foi du paiement.",
           8, False, GRIS, "C")

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{paiement.numero_recu}.pdf"
    pdf.output(str(chemin))
    return chemin