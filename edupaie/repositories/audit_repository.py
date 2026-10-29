import hashlib
import sqlite3

HASH_INITIAL = "0" * 64


def calculer_hash(precedent, date_heure, utilisateur_id, utilisateur, action,
                  objet, objet_id, detail) -> str:
    """Empreinte d'un événement : elle dépend de l'événement précédent (chaîne)."""
    morceaux = [precedent, date_heure,
                "" if utilisateur_id is None else str(utilisateur_id),
                utilisateur or "", action, objet or "",
                "" if objet_id is None else str(objet_id), detail or ""]
    return hashlib.sha256("\x1f".join(morceaux).encode("utf-8")).hexdigest()


class JournalRepository:
    """Accès aux données du journal d'audit (ajout seulement)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ajouter(self, date_heure, utilisateur_id, utilisateur, action, objet,
                objet_id, detail) -> int:
        with self.conn:  # commit ou rollback automatique
            dernier = self.conn.execute(
                "SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            precedent = dernier["hash"] if dernier else HASH_INITIAL
            empreinte = calculer_hash(precedent, date_heure, utilisateur_id, utilisateur,
                                      action, objet, objet_id, detail)
            cur = self.conn.execute(
                "INSERT INTO audit (date_heure, utilisateur_id, utilisateur, action, "
                "objet, objet_id, detail, hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (date_heure, utilisateur_id, utilisateur, action, objet, objet_id,
                 detail, empreinte))
        return cur.lastrowid

    def lister(self, debut, fin, motifs=None, utilisateur=None, recherche="",
               limite=2000):
        """Événements de la période, du plus récent au plus ancien."""
        sql = "SELECT * FROM audit WHERE date_heure BETWEEN ? AND ?"
        params = [f"{debut}T00:00:00", f"{fin}T23:59:59"]
        if motifs:
            sql += " AND (" + " OR ".join("action LIKE ?" for _ in motifs) + ")"
            params += list(motifs)
        if utilisateur:
            sql += " AND utilisateur = ?"
            params.append(utilisateur)
        if recherche:
            echappe = recherche.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            sql += " AND detail LIKE ? ESCAPE '\\'"
            params.append(f"%{echappe}%")
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        return self.conn.execute(sql, params).fetchall()

    def tout(self):
        return self.conn.execute("SELECT * FROM audit ORDER BY id")

    def sequence(self):
        ligne = self.conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'audit'").fetchone()
        return ligne[0] if ligne else None

    def utilisateurs(self) -> list[str]:
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT utilisateur FROM audit WHERE utilisateur IS NOT NULL "
            "ORDER BY utilisateur")]