from pathlib import Path

from openpyxl import Workbook

from edupaie.services.export_excel import _chemin, _ecrire


def _arrondi(taux):
    return None if taux is None else round(taux, 1)


def exporter_recouvrement(tableau, dossier) -> Path:
    """Deux feuilles : la situation par classe et l'évolution mois par mois."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Par classe"
    colonnes = [("Classe", "texte"), ("Élèves", "nombre"), ("Total dû (FCFA)", "montant"),
                ("Remises (FCFA)", "montant"), ("À payer (FCFA)", "montant"),
                ("Encaissé (FCFA)", "montant"), ("Reste (FCFA)", "montant"),
                ("Taux d'encaissement (%)", "nombre"),
                (f"Exigible au {tableau['date_ref']} (FCFA)", "montant"),
                ("En retard (FCFA)", "montant"), ("Élèves en retard", "nombre"),
                ("Soldés", "nombre"), ("Partiels", "nombre"), ("Non payés", "nombre")]

    def ligne(c):
        return [c["classe"], c["eleves"], c["total_du"], c["remises"], c["net"], c["paye"],
                c["reste"], _arrondi(c["taux"]), c["exigible"], c["retard"], c["en_retard"],
                c["soldes"], c["partiels"], c["non_payes"]]

    _ecrire(ws, colonnes, [ligne(c) for c in tableau["classes"]],
            ligne(tableau["total"]) if tableau["classes"] else None)

    ws2 = wb.create_sheet("Par mois")
    colonnes2 = [("Mois", "texte"), ("Encaissé (FCFA)", "montant"), ("Prévu (FCFA)", "montant"),
                 ("Taux du mois (%)", "nombre"), ("Encaissé cumulé (FCFA)", "montant"),
                 ("Prévu cumulé (FCFA)", "montant"), ("Taux cumulé (%)", "nombre")]
    lignes2 = []
    for m in tableau["mois"]:
        libelle = m["libelle"] + (" (en cours)" if m["en_cours"] else
                                  " (à venir)" if m["a_venir"] else "")
        lignes2.append([libelle, None if m["a_venir"] else m["encaisse"], m["prevu"],
                        _arrondi(m["taux"]),
                        None if m["a_venir"] else m["cumul_encaisse"], m["cumul_prevu"],
                        _arrondi(m["taux_cumule"])])
    _ecrire(ws2, colonnes2, lignes2)

    chemin = _chemin(dossier, f"recouvrement_{tableau['annee']}")
    wb.save(chemin)
    return chemin