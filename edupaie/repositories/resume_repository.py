import sqlite3

CLE_NUMERO = "whatsapp_direction"


class ResumeRepository:
    """Données du résumé de caisse : remises de la période et numéro WhatsApp de la direction."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def numero(self) -> str:
        ligne = self.conn.execute(
            "SELECT valeur FROM parametre WHERE cle = ?", (CLE_NUMERO,)).fetchone()
        return ligne["valeur"] if ligne else ""

    def definir_numero(self, valeur: str) -> None:
        with self.conn:  # commit ou rollback automatique
            if valeur:
                self.conn.execute(
                    "INSERT INTO parametre (cle, valeur) VALUES (?, ?) "
                    "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                    (CLE_NUMERO, valeur))
            else:
                self.conn.execute("DELETE FROM parametre WHERE cle = ?", (CLE_NUMERO,))

    def remises_periode(self, debut: str, fin: str):
        """Remises accordées (et non annulées) pendant la période."""
        return self.conn.execute(
            """SELECT r.id, r.montant, r.motif, e.nom, e.prenom, e.classe
               FROM remise r JOIN eleve e ON e.id = r.eleve_id
               WHERE r.annule = 0 AND substr(r.accorde_le, 1, 10) BETWEEN ? AND ?
               ORDER BY r.id""", (debut, fin)).fetchall()