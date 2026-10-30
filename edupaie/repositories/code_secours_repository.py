import sqlite3


class CodeSecoursRepository:
    """Empreintes des codes de secours (jamais les codes eux-mêmes)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def remplacer(self, utilisateur_id: int, empreintes: list[str]) -> None:
        """Remplace tous les codes de l'utilisateur, en une seule transaction."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM code_secours WHERE utilisateur_id = ?", (utilisateur_id,))
            self.conn.executemany(
                "INSERT INTO code_secours (utilisateur_id, empreinte) VALUES (?, ?)",
                [(utilisateur_id, e) for e in empreintes])

    def non_utilises(self, utilisateur_id: int):
        return self.conn.execute(
            "SELECT id, empreinte FROM code_secours "
            "WHERE utilisateur_id = ? AND utilise_le IS NULL ORDER BY id",
            (utilisateur_id,)).fetchall()

    def marquer_utilise(self, code_id: int, quand: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE code_secours SET utilise_le = ? WHERE id = ?", (quand, code_id))

    def compter_restants(self, utilisateur_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM code_secours "
            "WHERE utilisateur_id = ? AND utilise_le IS NULL", (utilisateur_id,)).fetchone()[0]