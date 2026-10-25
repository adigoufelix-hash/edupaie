from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from edupaie.services.recu_pdf import (BLANC, BORDURE, CLAIR, GRIS, INDIGO,
                                       LAVANDE, MARINE, MODES, _date_fr, _montant)

LARGEURS = (34, 20, 58, 20, 26, 28)  # reçu, date, élève, classe, mode, montant
TITRES = ["N° de reçu", "Date", "Élève", "Classe", "Mode", "Montant"]
ALIGNS = ["L", "L", "L", "L", "L", "R"]


def _l1(texte) -> str:
    """Helvetica ne gère que le latin-1 : on évite un plantage sur un nom exotique."""
    return str(texte).encode("latin-1", "replace").decode("latin-1")


def _court(texte, n) -> str:
    texte = str(texte)
    return texte if len(texte) <= n else texte[:n - 3] + "..."


def _periode(debut, fin) -> str:
    return _date_fr(debut) if debut == fin else f"du {_date_fr(debut)} au {_date_fr(fin)}"


class _PDF(FPDF):
    def __init__(self, periode):
        super().__init__(unit="mm", format="A4")
        self.periode = periode
        self.set_margins(12, 12, 12)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self):
        self.set_fill_color(*MARINE)
        self.rect(0, 0, 210, 22, style="F")
        self.set_text_color(*BLANC)
        self.set_xy(12, 6)
        self.set_font("Helvetica", "B", 16)
        self.cell(70, 8, "EduPaie")
        self.set_xy(90, 5)
        self.set_font("Helvetica", "B", 11)
        self.cell(108, 6, _l1("CLÔTURE DE CAISSE"), align="R")
        self.set_xy(90, 12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*LAVANDE)
        self.cell(108, 5, _l1(self.periode), align="R")
        self.set_y(28)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIS)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="C")


def _titre(pdf, texte):
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*INDIGO)
    pdf.cell(0, 7, _l1(texte))
    pdf.ln(8)


def _entete(pdf, titres, largeurs, aligns):
    pdf.set_fill_color(*MARINE)
    pdf.set_text_color(*BLANC)
    pdf.set_font("Helvetica", "B", 8)
    for titre, w, a in zip(titres, largeurs, aligns):
        pdf.cell(w, 7, _l1(titre), align=a, fill=True)
    pdf.ln(7)


def _ligne(pdf, valeurs, largeurs, aligns, gras=False, couleur=MARINE, fond=None):
    pdf.set_font("Helvetica", "B" if gras else "", 9)
    pdf.set_text_color(*couleur)
    if fond:
        pdf.set_fill_color(*fond)
    for v, w, a in zip(valeurs, largeurs, aligns):
        pdf.cell(w, 6.5, _l1(v), align=a, fill=bool(fond))
    pdf.ln(6.5)
    pdf.set_draw_color(*BORDURE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())


def _table_paiements(pdf, paiements, couleur=MARINE):
    _entete(pdf, TITRES, LARGEURS, ALIGNS)
    for p in paiements:
        if pdf.get_y() > pdf.h - 28:
            pdf.add_page()
            _entete(pdf, TITRES, LARGEURS, ALIGNS)
        valeurs = [p["numero_recu"] or "", _date_fr(p["date_paiement"]),
                   _court(f"{p['nom']} {p['prenom']}", 30), p["classe"],
                   MODES.get(p["mode"], p["mode"]), _montant(p["montant"])]
        _ligne(pdf, valeurs, LARGEURS, ALIGNS, couleur=couleur)


def generer_cloture_pdf(cloture: dict, dossier) -> Path:
    """Génère le PDF de clôture à partir du résultat de CaisseService.cloture()."""
    pdf = _PDF(_periode(cloture["debut"], cloture["fin"]))
    pdf.add_page()

    # Informations générales
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRIS)
    edite = datetime.now().strftime("%d/%m/%Y à %H:%M")
    if cloture.get("genere_par"):
        edite += f" par {cloture['genere_par']}"
    pdf.cell(0, 5, _l1(cloture["portee"]))
    pdf.ln(5)
    pdf.cell(0, 5, _l1(f"Édité le {edite}"))
    pdf.ln(9)

    # Total et nombre de paiements
    y = pdf.get_y()
    pdf.set_fill_color(*INDIGO)
    pdf.rect(12, y, 108, 24, style="F", round_corners=True, corner_radius=3)
    pdf.set_xy(12, y + 4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*LAVANDE)
    pdf.cell(108, 4, "TOTAL ENCAISSÉ".encode("latin-1").decode("latin-1"), align="C")
    pdf.set_xy(12, y + 10)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BLANC)
    pdf.cell(108, 10, _montant(cloture["total"]), align="C")
    pdf.set_fill_color(*CLAIR)
    pdf.set_draw_color(*BORDURE)
    pdf.rect(126, y, 72, 24, style="DF", round_corners=True, corner_radius=3)
    pdf.set_xy(126, y + 4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GRIS)
    pdf.cell(72, 4, "PAIEMENTS", align="C")
    pdf.set_xy(126, y + 10)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*MARINE)
    pdf.cell(72, 10, str(cloture["nb"]), align="C")
    pdf.set_y(y + 28)

    # Répartition par mode de paiement
    _titre(pdf, "Répartition par mode de paiement")
    larg, aligns = (126, 60), ["L", "R"]
    _entete(pdf, ["Mode", "Montant"], larg, aligns)
    for mode, montant in cloture["par_mode"].items():
        _ligne(pdf, [MODES.get(mode, mode), _montant(montant)], larg, aligns)
    _ligne(pdf, ["TOTAL", _montant(cloture["total"])], larg, aligns,
           gras=True, fond=CLAIR)

    # Détail par caissier
    for caissier in cloture["caissiers"]:
        _titre(pdf, f"Caissier : {caissier['nom']} - {caissier['nb']} paiement(s) - "
                    f"{_montant(caissier['total'])}")
        _table_paiements(pdf, caissier["paiements"])

    # Paiements annulés (non comptés)
    annules = cloture["annules"]
    if annules["nb"]:
        _titre(pdf, f"Paiements annulés (non comptés) : {annules['nb']} - "
                    f"{_montant(annules['total'])}")
        _table_paiements(pdf, annules["paiements"], couleur=GRIS)

    # Signatures
    if pdf.get_y() > pdf.h - 55:
        pdf.add_page()
    y = pdf.get_y() + 14
    pdf.set_draw_color(*GRIS)
    pdf.line(14, y + 14, 82, y + 14)
    pdf.line(128, y + 14, 196, y + 14)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRIS)
    pdf.set_xy(14, y + 16)
    pdf.cell(68, 5, "Visa du caissier", align="C")
    pdf.set_xy(128, y + 16)
    pdf.cell(68, 5, "Visa de la direction", align="C")

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"cloture_{cloture['debut']}_{cloture['fin']}.pdf"
    pdf.output(str(chemin))
    return chemin