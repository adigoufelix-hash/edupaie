import sqlite3
from edupaie.models.entities import Eleve


class EleveRepository:
    """Accès aux données de la table eleve. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @staticmethod
    def _to_eleve(row: sqlite3.Row) -> Eleve:
        return Eleve(**dict(row))

    def lister(self, recherche: str = "", classe: str | None = None) -> list[Eleve]:
        sql = "SELECT * FROM eleve WHERE (nom LIKE ? OR prenom LIKE ?)"
        params = [f"%{recherche}%", f"%{recherche}%"]
        if classe:
            sql += " AND classe = ?"
            params.append(classe)
        sql += " ORDER BY nom, prenom"
        return [self._to_eleve(r) for r in self.conn.execute(sql, params)]

    def get(self, eleve_id: int) -> Eleve | None:
        row = self.conn.execute(
            "SELECT * FROM eleve WHERE id = ?", (eleve_id,)).fetchone()
        return self._to_eleve(row) if row else None

    def classes(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT classe FROM eleve ORDER BY classe")
        return [r["classe"] for r in rows]

    def ajouter(self, e: Eleve) -> int:
        with self.conn:  # commit ou rollback automatique
         cur = self.conn.execute(
            "INSERT INTO eleve (nom, prenom, classe, annee_scolaire, total_du) "
            "VALUES (?, ?, ?, ?, ?)",
            (e.nom, e.prenom, e.classe, e.annee_scolaire, e.total_du))
        return cur.lastrowid

    def modifier(self, e: Eleve) -> None:
        self.conn.execute(
            "UPDATE eleve SET nom=?, prenom=?, classe=?, annee_scolaire=?, total_du=? "
            "WHERE id=?",
            (e.nom, e.prenom, e.classe, e.annee_scolaire, e.total_du, e.id))

    def supprimer(self, eleve_id: int) -> None:
        # Lève sqlite3.IntegrityError si l'élève a des paiements (ON DELETE RESTRICT)
        self.conn.execute("DELETE FROM eleve WHERE id = ?", (eleve_id,))