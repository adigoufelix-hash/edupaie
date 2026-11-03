import sqlite3


class ParametreRepository:
    """Petits réglages de l'application (table parametre : clé, valeur)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, cle: str):
        ligne = self.conn.execute(
            "SELECT valeur FROM parametre WHERE cle = ?", (cle,)).fetchone()
        return ligne["valeur"] if ligne else None

    def set(self, cle: str, valeur: str) -> None:
        with self.conn:  # commit ou rollback automatique
            self.conn.execute(
                "INSERT INTO parametre (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, valeur))

    def supprimer(self, cle: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM parametre WHERE cle = ?", (cle,))