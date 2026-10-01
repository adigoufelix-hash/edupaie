from pathlib import Path

from fpdf import FPDF

MODES = {
    "especes": "Espèces",
    "cheque": "Chèque",
    "virement": "Virement",
    "mobile_money": "Mobile money",
}


def _montant(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ") + " FCFA"


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


def generer_recu_pdf(eleve, paiement, dossier) -> Path:
    """Génère le reçu PDF. Il n'utilise que des données enregistrées
    (jamais l'heure d'impression), donc la ré-impression est identique."""
    pdf = FPDF(format="A5")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    def ligne(libelle: str, valeur: str):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(55, 8, libelle)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, valeur, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "EduPaie", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, "REÇU DE PAIEMENT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"N° {paiement.numero_recu}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    ligne("Élève :", f"{eleve.nom} {eleve.prenom}")
    ligne("Classe :", eleve.classe)
    ligne("Année scolaire :", eleve.annee_scolaire)
    pdf.ln(3)
    ligne("Date du paiement :", _date_fr(paiement.date_paiement))
    ligne("Mode de paiement :", MODES.get(paiement.mode, paiement.mode))
    ligne("Total des frais :", _montant(eleve.total_du))
    ligne("Montant payé :", _montant(paiement.montant))
    ligne("Solde restant :", _montant(paiement.solde_apres))

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Merci de conserver ce reçu.", align="C")

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{paiement.numero_recu}.pdf"
    pdf.output(str(chemin))
    return chemin