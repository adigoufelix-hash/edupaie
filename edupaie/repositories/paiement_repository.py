import sqlite3
from edupaie.models.entities import Paiement


class PaiementRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @staticmethod
    def _vers_paiement(row) -> Paiement:
        return Paiement(
            id=row["id"], eleve_id=row["eleve_id"],
            numero_recu=row["numero_recu"], montant=row["montant"],
            date_paiement=row["date_paiement"], mode=row["mode"],
            solde_apres=row["solde_apres"],
        )
    def ajouter(self, p: Paiement) -> int:
        """Insère le paiement et lui attribue son numéro de reçu (même transaction)."""
        with self.conn:  # commit ou rollback automatique
            cur = self.conn.execute(
                """INSERT INTO paiement
                   (eleve_id, montant, date_paiement, mode, solde_apres)
                   VALUES (?, ?, ?, ?, ?)""",
                (p.eleve_id, p.montant, p.date_paiement, p.mode, p.solde_apres),
            )
            paiement_id = cur.lastrowid
            numero = f"REC-{p.date_paiement[:4]}-{paiement_id:06d}"
            self.conn.execute(
                "UPDATE paiement SET numero_recu = ? WHERE id = ?",
                (numero, paiement_id),
            )
        return paiement_id

    def lister_par_eleve(self, eleve_id: int) -> list[Paiement]:
        rows = self.conn.execute(
            """SELECT * FROM paiement WHERE eleve_id = ?
               ORDER BY date_paiement, id""",
            (eleve_id,),
        ).fetchall()
        return [self._vers_paiement(r) for r in rows]

    def obtenir(self, paiement_id: int) -> Paiement | None:
        row = self.conn.execute(
            "SELECT * FROM paiement WHERE id = ?", (paiement_id,)
        ).fetchone()
        return self._vers_paiement(row) if row else None

    def total_paye(self, eleve_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(montant), 0) AS total FROM paiement WHERE eleve_id = ?",
            (eleve_id,),
        ).fetchone()
        return row["total"]
