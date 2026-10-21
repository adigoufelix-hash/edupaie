class UtilisateurRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_by_login(self, login: str):
        return self.conn.execute(
            "SELECT * FROM utilisateur WHERE login = ? AND actif = 1", (login,)
        ).fetchone()

    def creer(self, login: str, nom_complet: str, mot_de_passe_hash: str, role: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO utilisateur (login, nom_complet, mot_de_passe, role) "
            "VALUES (?, ?, ?, ?)",
            (login, nom_complet, mot_de_passe_hash, role),
        )
        self.conn.commit()
        return cur.lastrowid

    def compter(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM utilisateur").fetchone()[0]