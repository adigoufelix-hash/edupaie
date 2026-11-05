import sqlite3

from edupaie.repositories.classe_repository import lister_noms


class RecouvrementRepository:
    """Lectures pour le tableau de recouvrement. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def annees(self) -> list[str]:
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT annee_scolaire FROM eleve ORDER BY annee_scolaire DESC")]

    def classes_ordonnees(self) -> list[str]:
        return lister_noms(self.conn)

    def eleves(self, annee: str):
        """Les élèves de l'année avec le total de leurs remises et de leurs paiements valides."""
        return self.conn.execute(
            """SELECT e.id, e.classe, e.total_du,
                      COALESCE((SELECT SUM(r.montant) FROM remise r
                                WHERE r.eleve_id = e.id AND r.annule = 0), 0) AS remises,
                      COALESCE((SELECT SUM(p.montant) FROM paiement p
                                WHERE p.eleve_id = e.id AND p.annule = 0), 0) AS paye
               FROM eleve e WHERE e.annee_scolaire = ?
               ORDER BY e.id""", (annee,)).fetchall()

    def echeances(self, annee: str):
        return self.conn.execute(
            "SELECT classe, date_limite, pourcentage FROM echeance "
            "WHERE annee_scolaire = ? ORDER BY classe, date_limite, id", (annee,)).fetchall()

    def paiements_par_mois(self, annee: str):
        """Paiements valides des élèves de l'année, regroupés par mois (AAAA-MM)."""
        return self.conn.execute(
            """SELECT substr(p.date_paiement, 1, 7) AS mois, SUM(p.montant) AS montant
               FROM paiement p JOIN eleve e ON e.id = p.eleve_id
               WHERE e.annee_scolaire = ? AND p.annule = 0
               GROUP BY mois ORDER BY mois""", (annee,)).fetchall()