from datetime import datetime
from itertools import groupby
from pathlib import Path

from fpdf import FPDF

from edupaie.services.cloture_pdf import _entete, _l1, _ligne, _titre
from edupaie.services.recu_pdf import BLANC, GRIS, LAVANDE, MARINE, _date_fr, _montant
from edupaie.services.ecole import courant
from edupaie.services.pdf_commun import adapter, dessiner_logo

LARGEURS = (58, 40, 24, 16, 32, 32, 32, 39)
TITRES = ["Élève", "Échéance impayée", "Date limite", "Jours", "Exigible",
          "Payé", "En retard", "Téléphone"]
ALIGNS = ["L", "L", "L", "C", "R", "R", "R", "L"]


class _PDF(FPDF):
    def __init__(self, sous_titre, ecole):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.sous_titre = sous_titre
        self.ecole = ecole
        self.set_margins(12, 12, 12)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self):
        self.set_fill_color(*MARINE)
        self.rect(0, 0, 297, 22, style="F")
        x_texte = 32 if dessiner_logo(self, self.ecole.logo, 12, 3, 16) else 12
        nom, taille = adapter(self, self.ecole.nom_affiche, 112 - x_texte, 16, 8)
        self.set_text_color(*BLANC)
        self.set_xy(x_texte, 6)
        self.set_font("Helvetica", "B", taille)
        self.cell(112 - x_texte, 8, nom)
        self.set_xy(120, 5)
        self.set_font("Helvetica", "B", 11)
        self.cell(165, 6, _l1("ÉLÈVES EN RETARD DE PAIEMENT"), align="R")
        self.set_xy(120, 12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*LAVANDE)
        self.cell(165, 5, _l1(self.sous_titre), align="R")
        self.set_y(28)
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIS)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="C")


def generer_impayes_pdf(resultat, dossier, ecole=None) -> Path:
    pdf = _PDF(f"au {_date_fr(resultat['date_ref'])}", ecole or courant())
    pdf.add_page()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRIS)
    pdf.cell(0, 5, _l1(f"Édité le {datetime.now():%d/%m/%Y à %H:%M}"))
    pdf.ln(7)

    lignes = resultat["lignes"]
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*MARINE)
    if lignes:
        pdf.cell(0, 7, _l1(f"Total en retard : {_montant(resultat['total_retard'])} "
                           f"- {len(lignes)} élève(s)"))
    else:
        pdf.cell(0, 7, _l1("Aucun élève en retard à cette date."))
    pdf.ln(8)

    for classe, groupe in groupby(sorted(lignes, key=lambda l: (l["classe"], l["nom"])),
                                  key=lambda l: l["classe"]):
        groupe = list(groupe)
        _titre(pdf, f"{classe} - {len(groupe)} élève(s) - "
                    f"{_montant(sum(l['retard'] for l in groupe))}")
        _entete(pdf, TITRES, LARGEURS, ALIGNS)
        for l in groupe:
            if pdf.get_y() > pdf.h - 28:
                pdf.add_page()
                _entete(pdf, TITRES, LARGEURS, ALIGNS)
            _ligne(pdf, [l["nom"][:30], l["tranche"][:22], _date_fr(l["date_limite"]),
                         str(l["jours"]), _montant(l["exigible"]), _montant(l["paye"]),
                         _montant(l["retard"]), l["telephone"] or "-"],
                   LARGEURS, ALIGNS)

    if resultat["sans_echeancier"]:
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRIS)
        pdf.cell(0, 5, _l1(f"{resultat['sans_echeancier']} élève(s) appartiennent à des "
                           "classes sans échéancier : ils ne sont pas suivis ici."))

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"impayes_{resultat['date_ref']}.pdf"
    pdf.output(str(chemin))
    return chemin