from edupaie.db.connection import  transaction


def get_by_login(login: str):
    with transaction() as con:
        return con.execute(
            "SELECT * FROM utilisateur WHERE login = ? AND actif = 1", (login,)
        ).fetchone()


def creer(login: str, nom_complet: str, mot_de_passe_hash: str, role: str) -> int:
    with transaction() as con:
        cur = con.execute(
            "INSERT INTO utilisateur (login, nom_complet, mot_de_passe, role) "
            "VALUES (?, ?, ?, ?)",
            (login, nom_complet, mot_de_passe_hash, role),
        )
        return cur.lastrowid


def compter() -> int:
    with transaction() as con:
        return con.execute("SELECT COUNT(*) FROM utilisateur").fetchone()[0]