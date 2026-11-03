import sqlite3

from edupaie.repositories.classe_repository import lister_noms

TABLES = {"eleve", "frais_classe", "echeance", "utilisateur"}


class DemarrageRepository:
    """Quelques comptages pour la liste « Pour bien démarrer »."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def compter(self, table: str) -> int:
        if table not in TABLES:
            raise ValueError(table)
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def classes(self) -> list[str]:
        return lister_noms(self.conn)