import sqlite3


class EcoleRepository:
    """Accès aux données de la table ecole (une seule ligne). Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def lire(self):
        return self.conn.execute(
            "SELECT nom, adresse, telephone, email, logo FROM ecole WHERE id = 1"
        ).fetchone()

    def enregistrer(self, nom, adresse, telephone, email, logo) -> None:
        with self.conn:  # commit ou rollback automatique
            self.conn.execute(
                """INSERT INTO ecole (id, nom, adresse, telephone, email, logo)
                   VALUES (1, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       nom = excluded.nom, adresse = excluded.adresse,
                       telephone = excluded.telephone, email = excluded.email,
                       logo = excluded.logo""",
                (nom, adresse, telephone, email, logo))