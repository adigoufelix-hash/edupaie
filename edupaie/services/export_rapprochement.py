from pathlib import Path

from openpyxl import Workbook

from edupaie.services.export_excel import _chemin, _date, _ecrire
from edupaie.services.rapprochement_service import ETATS


def _fr(iso):
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


def exporter_rapprochement(analyse, dossier) -> Path:
    """Trois feuilles : le relevé, les paiements sans trace et le résumé."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Relevé"
    colonnes = [("Date", "date"), ("Montant (FCFA)", "montant"), ("Référence", "texte"),
                ("Libellé", "texte"), ("État", "texte"), ("Reçu", "texte"),
                ("Élève", "texte"), ("Classe", "texte"), ("Caissier", "texte"),
                ("Motif", "texte")]
    lignes = []
    for l in analyse["lignes"]:
        p = l["paiement"] or l["proposition"] or {}
        lignes.append([_date(l["date"]), l["montant"], l["reference"], l["libelle"],
                       ETATS[l["etat"]], p.get("numero_recu", ""), p.get("eleve", ""),
                       p.get("classe", ""), p.get("caissier", ""), l["motif"]])
    _ecrire(ws, colonnes, lignes)

    ws2 = wb.create_sheet("Sans trace")
    colonnes2 = [("Reçu", "texte"), ("Date du paiement", "date"), ("Montant (FCFA)", "montant"),
                 ("Élève", "texte"), ("Classe", "texte"), ("Caissier", "texte")]
    lignes2 = [[p["numero_recu"], _date(p["date_paiement"]), p["montant"], p["eleve"],
                p["classe"], p["caissier"]] for p in analyse["sans_trace"]]
    _ecrire(ws2, colonnes2, lignes2)

    r = analyse["resume"]
    ws3 = wb.create_sheet("Résumé")
    lignes3 = [
        ["Période", f"{_fr(analyse['debut'])} au {_fr(analyse['fin'])}"],
        ["Opérations du relevé (hors ignorées)", r["nb_lignes"]],
        ["Montant du relevé (FCFA)", r["montant_releve"]],
        ["Opérations rapprochées", r["nb_rapproche"]],
        ["Montant rapproché (FCFA)", r["montant_rapproche"]],
        ["Écart (relevé non rapproché)", r["ecart"]],
        ["Opérations sans paiement enregistré", r["nb_sans_paiement"]],
        ["Paiements mobile money sans trace sur le relevé", r["nb_sans_trace"]],
        ["Montant des paiements sans trace (FCFA)", r["montant_sans_trace"]],
        ["Paiements annulés après rapprochement", r["nb_alertes"]],
        ["Opérations ignorées", r["nb_ignore"]],
    ]
    _ecrire(ws3, [("Indicateur", "texte"), ("Valeur", "nombre")], lignes3)

    chemin = _chemin(dossier, "rapprochement_mobile_money")
    wb.save(chemin)
    return chemin