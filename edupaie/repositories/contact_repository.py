import sqlite3


class ContactRepository:
    """Contact du parent ou tuteur d'un élève."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, eleve_id: int):
        return self.conn.execute(
            "SELECT tuteur, telephone FROM contact_eleve WHERE eleve_id = ?",
            (eleve_id,)).fetchone()

    def enregistrer(self, eleve_id: int, tuteur: str, telephone: str) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO contact_eleve (eleve_id, tuteur, telephone)
                   VALUES (?, ?, ?)
                   ON CONFLICT(eleve_id) DO UPDATE SET
                       tuteur = excluded.tuteur, telephone = excluded.telephone""",
                (eleve_id, tuteur, telephone))