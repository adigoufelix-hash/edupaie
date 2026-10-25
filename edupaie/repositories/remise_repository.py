import sqlite3


class RemiseRepository:
    """Accès aux données de la table remise. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ajouter(self, eleve_id, type_, valeur, montant, motif, par, quand) -> int:
        with self.conn:  # commit ou rollback automatique
            cur = self.conn.execute(
                """INSERT INTO remise
                   (eleve_id, type, valeur, montant, motif, accorde_par, accorde_le)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (eleve_id, type_, valeur, montant, motif, par, quand))
        return cur.lastrowid

    def obtenir(self, remise_id: int):
        return self.conn.execute(
            "SELECT * FROM remise WHERE id = ?", (remise_id,)).fetchone()

    def lister_par_eleve(self, eleve_id: int):
        """Toutes les remises, annulées comprises (elles restent visibles)."""
        return self.conn.execute(
            "SELECT * FROM remise WHERE eleve_id = ? ORDER BY id", (eleve_id,)
        ).fetchall()

    def annuler(self, remise_id: int, motif: str, par: str | None, quand: str) -> None:
        with self.conn:
            self.conn.execute(
                """UPDATE remise SET annule = 1, motif_annulation = ?,
                   annule_par = ?, annule_le = ? WHERE id = ?""",
                (motif, par, quand, remise_id))