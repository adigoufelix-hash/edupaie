import sqlite3


class UtilisateurRepository:
    """Accès aux données de la table utilisateur. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def compter(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM utilisateur").fetchone()[0]

    def compter_admins(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM utilisateur WHERE role = 'admin'").fetchone()[0]

    def get_by_login(self, login: str):
        return self.conn.execute(
            "SELECT * FROM utilisateur WHERE login = ? COLLATE NOCASE", (login,)).fetchone()

    def get(self, utilisateur_id: int):
        return self.conn.execute(
            "SELECT * FROM utilisateur WHERE id = ?", (utilisateur_id,)).fetchone()

    def lister(self):
        return self.conn.execute(
            "SELECT id, login, nom_complet, role, doit_changer_mdp "
            "FROM utilisateur ORDER BY login").fetchall()

    def creer(self, login: str, nom_complet: str, mot_de_passe: str, role: str,
              doit_changer: bool = False) -> int:
        with self.conn:  # commit ou rollback automatique
            cur = self.conn.execute(
                "INSERT INTO utilisateur (login, nom_complet, mot_de_passe, role, "
                "doit_changer_mdp) VALUES (?, ?, ?, ?, ?)",
                (login, nom_complet, mot_de_passe, role, int(doit_changer)))
        return cur.lastrowid

    def maj_mot_de_passe(self, utilisateur_id: int, valeur: str,
                         doit_changer: bool | None = None) -> None:
        """doit_changer : None laisse l'obligation de changement telle quelle."""
        with self.conn:
            if doit_changer is None:
                self.conn.execute(
                    "UPDATE utilisateur SET mot_de_passe = ? WHERE id = ?",
                    (valeur, utilisateur_id))
            else:
                self.conn.execute(
                    "UPDATE utilisateur SET mot_de_passe = ?, doit_changer_mdp = ? "
                    "WHERE id = ?", (valeur, int(doit_changer), utilisateur_id))

    def supprimer(self, utilisateur_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM utilisateur WHERE id = ?", (utilisateur_id,))