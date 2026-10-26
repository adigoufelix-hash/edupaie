import sqlite3


class EcheanceRepository:
    """Accès aux données de la table echeance. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def lister(self, classe: str, annee: str):
        return self.conn.execute(
            "SELECT id, libelle, date_limite, pourcentage FROM echeance "
            "WHERE classe = ? AND annee_scolaire = ? ORDER BY date_limite, id",
            (classe, annee)).fetchall()

    def obtenir(self, echeance_id: int):
        return self.conn.execute(
            "SELECT * FROM echeance WHERE id = ?", (echeance_id,)).fetchone()

    def total_pourcentage(self, classe: str, annee: str, sauf_id: int | None = None) -> int:
        return self.conn.execute(
            "SELECT COALESCE(SUM(pourcentage), 0) FROM echeance "
            "WHERE classe = ? AND annee_scolaire = ? AND id != ?",
            (classe, annee, -1 if sauf_id is None else sauf_id)).fetchone()[0]

    def ajouter(self, classe, annee, libelle, date_limite, pourcentage) -> int:
        with self.conn:  # commit ou rollback automatique
            cur = self.conn.execute(
                "INSERT INTO echeance (classe, annee_scolaire, libelle, date_limite, pourcentage) "
                "VALUES (?, ?, ?, ?, ?)",
                (classe, annee, libelle, date_limite, pourcentage))
        return cur.lastrowid

    def modifier(self, echeance_id, libelle, date_limite, pourcentage) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE echeance SET libelle = ?, date_limite = ?, pourcentage = ? WHERE id = ?",
                (libelle, date_limite, pourcentage, echeance_id))

    def supprimer(self, echeance_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM echeance WHERE id = ?", (echeance_id,))