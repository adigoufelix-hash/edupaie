import sqlite3


def lister_noms(conn) -> list[str]:
    """Classes de l'école dans l'ordre choisi ; les classes présentes seulement dans
    les données (élèves, frais, échéancier) sont ajoutées à la suite."""
    noms = [r[0] for r in conn.execute(
        "SELECT nom FROM classe ORDER BY ordre, nom COLLATE NOCASE")]
    connus = {n.casefold() for n in noms}
    autres = conn.execute(
        "SELECT classe FROM eleve UNION SELECT classe FROM frais_classe "
        "UNION SELECT classe FROM echeance").fetchall()
    for classe in sorted((r[0] for r in autres if r[0]), key=str.casefold):
        if classe.casefold() not in connus:
            noms.append(classe)
            connus.add(classe.casefold())
    return noms


class ClasseRepository:
    """Accès aux données des classes. Aucune règle métier ici."""

    TABLES = (("eleve", "classe"), ("frais_classe", "classe"), ("echeance", "classe"))

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def noms(self) -> list[str]:
        return lister_noms(self.conn)

    def utilisation(self) -> dict:
        """nom en minuscules -> (élèves, lignes de frais, tranches d'échéancier)."""
        resultat = {}
        for rang, (table, colonne) in enumerate(self.TABLES):
            lignes = self.conn.execute(
                f"SELECT {colonne}, COUNT(*) FROM {table} GROUP BY {colonne}")
            for classe, nombre in lignes:
                if classe:
                    compteurs = resultat.setdefault(classe.casefold(), [0, 0, 0])
                    compteurs[rang] += nombre
        return {cle: tuple(valeurs) for cle, valeurs in resultat.items()}

    def ajouter(self, nom: str) -> None:
        with self.conn:  # commit ou rollback automatique
            self.conn.execute(
                "INSERT INTO classe (nom, ordre) VALUES (?, "
                "(SELECT COALESCE(MAX(ordre), 0) + 1 FROM classe))", (nom,))

    def renommer(self, ancien: str, nouveau: str) -> None:
        """Renomme la classe partout, en une seule transaction."""
        with self.conn:
            for table, colonne in self.TABLES:
                self.conn.execute(
                    f"UPDATE {table} SET {colonne} = ? WHERE {colonne} = ? COLLATE NOCASE",
                    (nouveau, ancien))
            self.conn.execute(
                "INSERT OR IGNORE INTO classe (nom, ordre) VALUES (?, "
                "(SELECT COALESCE(MAX(ordre), 0) + 1 FROM classe))", (ancien,))
            self.conn.execute(
                "UPDATE classe SET nom = ? WHERE nom = ? COLLATE NOCASE", (nouveau, ancien))

    def supprimer(self, nom: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM classe WHERE nom = ? COLLATE NOCASE", (nom,))

    def deplacer(self, nom: str, delta: int) -> bool:
        """Échange la classe avec sa voisine ; renumérote toute la liste."""
        noms = lister_noms(self.conn)
        cles = [n.casefold() for n in noms]
        if nom.casefold() not in cles:
            return False
        i = cles.index(nom.casefold())
        j = i + delta
        if not 0 <= j < len(noms):
            return False
        noms[i], noms[j] = noms[j], noms[i]
        with self.conn:
            for rang, n in enumerate(noms, start=1):
                self.conn.execute(
                    "INSERT INTO classe (nom, ordre) VALUES (?, ?) "
                    "ON CONFLICT(nom) DO UPDATE SET ordre = excluded.ordre", (n, rang))
        return True