import sqlite3


class RelanceRepository:
    """Historique des relances. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ajouter(self, eleve_id, quand, montant, tranche, par) -> None:
        with self.conn:  # commit ou rollback automatique
            self.conn.execute(
                """INSERT INTO relance (eleve_id, date_relance, montant_retard, tranche, envoye_par)
                   VALUES (?, ?, ?, ?, ?)""", (eleve_id, quand, montant, tranche, par))

    def dernieres(self, eleve_ids) -> dict:
        """{id de l'élève : date de sa dernière relance}."""
        ids, resultat = list(eleve_ids), {}
        for debut in range(0, len(ids), 500):
            morceau = ids[debut:debut + 500]
            marques = ",".join("?" * len(morceau))
            for ligne in self.conn.execute(
                    f"SELECT eleve_id, MAX(date_relance) FROM relance "
                    f"WHERE eleve_id IN ({marques}) GROUP BY eleve_id", morceau):
                resultat[ligne[0]] = ligne[1]
        return resultat

    def historique(self, eleve_id):
        return self.conn.execute(
            "SELECT date_relance, montant_retard, tranche, envoye_par FROM relance "
            "WHERE eleve_id = ? ORDER BY date_relance DESC", (eleve_id,)).fetchall()