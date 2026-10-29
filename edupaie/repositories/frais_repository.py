import sqlite3

from edupaie.repositories.classe_repository import lister_noms


class FraisRepository:
    """Accès aux données de la table frais_classe. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def lister(self, classe: str, annee: str):
        return self.conn.execute(
            "SELECT id, libelle, montant FROM frais_classe "
            "WHERE classe = ? AND annee_scolaire = ? ORDER BY id",
            (classe, annee)).fetchall()

    def total(self, classe: str, annee: str) -> int:
        return self.conn.execute(
            "SELECT COALESCE(SUM(montant), 0) FROM frais_classe "
            "WHERE classe = ? AND annee_scolaire = ?", (classe, annee)).fetchone()[0]

    def classes(self) -> list[str]:
        return lister_noms(self.conn)

    def ajouter(self, classe: str, annee: str, libelle: str, montant: int) -> int:
        with self.conn:  # commit ou rollback automatique
            cur = self.conn.execute(
                "INSERT INTO frais_classe (classe, annee_scolaire, libelle, montant) "
                "VALUES (?, ?, ?, ?)", (classe, annee, libelle, montant))
        return cur.lastrowid

    def modifier(self, frais_id: int, libelle: str, montant: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE frais_classe SET libelle = ?, montant = ? WHERE id = ?",
                (libelle, montant, frais_id))

    def supprimer(self, frais_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM frais_classe WHERE id = ?", (frais_id,))