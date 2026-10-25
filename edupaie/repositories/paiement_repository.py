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
            utilisateur_id=row["utilisateur_id"],
            encaisse_par=row["encaisse_par"],
            annule=row["annule"],
            motif_annulation=row["motif_annulation"],
            annule_par=row["annule_par"],
            annule_le=row["annule_le"],
        )

    def ajouter(self, p: Paiement) -> int:
        """Insère le paiement et lui attribue son numéro de reçu (même transaction)."""
        with self.conn:  # commit ou rollback automatique
            cur = self.conn.execute(
                """INSERT INTO paiement
                   (eleve_id, montant, date_paiement, mode, solde_apres,
                    utilisateur_id, encaisse_par)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (p.eleve_id, p.montant, p.date_paiement, p.mode, p.solde_apres,
                 p.utilisateur_id, p.encaisse_par),
            )
            paiement_id = cur.lastrowid
            numero = f"REC-{p.date_paiement[:4]}-{paiement_id:06d}"
            self.conn.execute(
                "UPDATE paiement SET numero_recu = ? WHERE id = ?",
                (numero, paiement_id),
            )
        return paiement_id

    def annuler(self, paiement_id: int, motif: str, par: str | None, quand: str) -> None:
        """Marque le paiement annulé (jamais supprimé) et recalcule les soldes."""
        with self.conn:
            row = self.conn.execute(
                "SELECT eleve_id FROM paiement WHERE id = ?", (paiement_id,)
            ).fetchone()
            self.conn.execute(
                """UPDATE paiement SET annule = 1, motif_annulation = ?,
                   annule_par = ?, annule_le = ? WHERE id = ?""",
                (motif, par, quand, paiement_id),
            )
            self._recalculer_soldes(row["eleve_id"])

    def _recalculer_soldes(self, eleve_id: int) -> None:
        total_du = self.conn.execute(
            "SELECT total_du FROM eleve WHERE id = ?", (eleve_id,)).fetchone()[0]
        cumul = 0
        valides = self.conn.execute(
            """SELECT id, montant FROM paiement
               WHERE eleve_id = ? AND annule = 0
               ORDER BY date_paiement, id""",
            (eleve_id,),
        ).fetchall()
        for p in valides:
            cumul += p["montant"]
            self.conn.execute(
                "UPDATE paiement SET solde_apres = ? WHERE id = ?",
                (max(total_du - cumul, 0), p["id"]),
            )

    def lister_par_eleve(self, eleve_id: int) -> list[Paiement]:
        """Tous les paiements, annulés compris (ils restent visibles)."""
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
            """SELECT COALESCE(SUM(montant), 0) AS total FROM paiement
               WHERE eleve_id = ? AND annule = 0""",
            (eleve_id,),
        ).fetchone()
        return row["total"]

    def derniers(self, limite: int = 6) -> list[Paiement]:
        rows = self.conn.execute(
            """SELECT * FROM paiement WHERE annule = 0
               ORDER BY date_paiement DESC, id DESC LIMIT ?""",
            (limite,)).fetchall()
        return [self._vers_paiement(r) for r in rows]
    
    def lister_periode(self, debut: str, fin: str, utilisateur_id: int | None = None):
        """Paiements d'une période (annulés compris), avec le nom de l'élève."""
        sql = """SELECT p.id, p.numero_recu, p.date_paiement, p.mode, p.montant,
                        p.encaisse_par, p.utilisateur_id, p.annule,
                        p.motif_annulation, p.annule_par, p.annule_le,
                        e.nom, e.prenom, e.classe
                 FROM paiement p JOIN eleve e ON e.id = p.eleve_id
                 WHERE p.date_paiement BETWEEN ? AND ?"""
        params = [debut, fin]
        if utilisateur_id is not None:
            sql += " AND p.utilisateur_id = ?"
            params.append(utilisateur_id)
        sql += " ORDER BY p.date_paiement, p.id"
        return self.conn.execute(sql, params).fetchall()