import sqlite3


class ImportRepository:
    """Insertion en lot d'élèves. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ajouter_lot(self, eleves: list[dict]) -> int:
        with self.conn:  # une seule transaction : tout ou rien
            for e in eleves:
                cur = self.conn.execute(
                    "INSERT INTO eleve (nom, prenom, classe, annee_scolaire, total_du) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (e["nom"], e["prenom"], e["classe"], e["annee"], e["total"]))
                if e["tuteur"] or e["telephone"]:
                    self.conn.execute(
                        "INSERT INTO contact_eleve (eleve_id, tuteur, telephone) "
                        "VALUES (?, ?, ?)", (cur.lastrowid, e["tuteur"], e["telephone"]))
        return len(eleves)