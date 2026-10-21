from edupaie.db.connection import get_connection


def get_by_login(login: str):
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM utilisateur WHERE login = ? AND actif = 1", (login,)
        ).fetchone()


def creer(login: str, nom_complet: str, mot_de_passe_hash: str, role: str) -> int:
    with get_connection() as con:
        cur = con.execute(
            "INSERT INTO utilisateur (login, nom_complet, mot_de_passe, role) "
            "VALUES (?, ?, ?, ?)",
            (login, nom_complet, mot_de_passe_hash, role),
        )
        return cur.lastrowid


def compter() -> int:
    with get_connection() as con:
        return con.execute("SELECT COUNT(*) FROM utilisateur").fetchone()[0]