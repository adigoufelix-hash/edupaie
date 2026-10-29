from openpyxl import Workbook

from edupaie.services.audit import LIBELLES
from edupaie.services.export_excel import _chemin, _ecrire


def exporter_journal(lignes, dossier):
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Journal d'audit"
    colonnes = [("Date et heure", "texte"), ("Utilisateur", "texte"),
                ("Action", "texte"), ("Détail", "texte")]
    donnees = [[l["date_heure"].replace("T", " "), l["utilisateur"] or "-",
                LIBELLES.get(l["action"], l["action"]), l["detail"]]
               for l in reversed(list(lignes))]  # ordre chronologique
    _ecrire(feuille, colonnes, donnees)
    chemin = _chemin(dossier, "journal")
    classeur.save(chemin)
    return chemin