from openpyxl import Workbook

from edupaie.services.export_excel import _chemin, _ecrire


def exporter_passage(resultat, dossier):
    """Rapport Excel du passage : qui est allé où, avec quel arriéré."""
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = f"Passage {resultat['cible']}"
    colonnes = [("Élève", "texte"), ("Ancienne classe", "texte"),
                ("Nouvelle classe", "texte"), ("Arriéré reporté (FCFA)", "montant"),
                ("Nouveau total (FCFA)", "montant")]
    lignes = [[f"{l['nom']} {l['prenom']}", l["classe_source"], l["classe_cible"],
               l["arrieres"], l["total"]] for l in resultat["lignes"]]
    total = ["TOTAL", None, None, sum(l[3] for l in lignes), sum(l[4] for l in lignes)]
    _ecrire(feuille, colonnes, lignes, total)
    chemin = _chemin(dossier, f"passage_{resultat['source']}_vers_{resultat['cible']}")
    classeur.save(chemin)
    return chemin