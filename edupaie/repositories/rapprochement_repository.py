import sqlite3


class RapprochementRepository:
    """Lectures et écritures de la table releve_mm. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ajouter_lignes(self, lignes, operateur, par, quand):
        """lignes : [(empreinte, opération)]. Retourne (importées, déjà présentes)."""
        importees = 0
        with self.conn:  # tout ou rien
            for empreinte, l in lignes:
                curseur = self.conn.execute(
                    """INSERT OR IGNORE INTO releve_mm
                       (empreinte, operateur, date_operation, montant, reference, libelle,
                        importe_par, importe_le)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (empreinte, operateur, l["date"], l["montant"], l.get("reference"),
                     l.get("libelle"), par, quand))
                importees += curseur.rowcount
        return importees, len(lignes) - importees

    def bornes(self):
        ligne = self.conn.execute(
            "SELECT MIN(date_operation), MAX(date_operation) FROM releve_mm").fetchone()
        return (ligne[0], ligne[1]) if ligne and ligne[0] else None

    def lignes(self, debut, fin):
        return self.conn.execute(
            """SELECT l.id, l.date_operation, l.montant, l.reference, l.libelle, l.statut,
                      l.paiement_id, l.motif, p.numero_recu, p.date_paiement,
                      p.annule AS paiement_annule, p.encaisse_par, e.nom, e.prenom, e.classe
               FROM releve_mm l
               LEFT JOIN paiement p ON p.id = l.paiement_id
               LEFT JOIN eleve e ON e.id = p.eleve_id
               WHERE l.date_operation BETWEEN ? AND ?
               ORDER BY l.date_operation, l.id""", (debut, fin)).fetchall()

    def ligne(self, ligne_id):
        return self.conn.execute(
            "SELECT * FROM releve_mm WHERE id = ?", (ligne_id,)).fetchone()

    def paiements_mm(self, debut, fin):
        """Paiements mobile money valides de la période, avec « lie » = déjà rapproché."""
        return self.conn.execute(
            """SELECT p.id, p.numero_recu, p.montant, p.date_paiement, p.encaisse_par, p.reference,
                      e.nom, e.prenom, e.classe, p.reference,
                      EXISTS (SELECT 1 FROM releve_mm l WHERE l.paiement_id = p.id) AS lie
               FROM paiement p JOIN eleve e ON e.id = p.eleve_id
               WHERE p.mode = 'mobile_money' AND p.annule = 0
                 AND p.date_paiement BETWEEN ? AND ?
               ORDER BY p.date_paiement, p.id""", (debut, fin)).fetchall()

    def paiement(self, paiement_id):
        return self.conn.execute(
            """SELECT p.id, p.numero_recu, p.montant, p.mode, p.annule, p.reference,
                      EXISTS (SELECT 1 FROM releve_mm l WHERE l.paiement_id = p.id) AS lie
               FROM paiement p WHERE p.id = ?""", (paiement_id,)).fetchone()

    def lier_plusieurs(self, liens, par, quand) -> None:
        """liens : [(ligne_id, paiement_id)]. Tout ou rien ; LookupError si une ligne a
        déjà été traitée, sqlite3.IntegrityError si un paiement est déjà rapproché."""
        with self.conn:
            for ligne_id, paiement_id in liens:
                curseur = self.conn.execute(
                    """UPDATE releve_mm SET statut = 'rapproche', paiement_id = ?, motif = NULL,
                              traite_par = ?, traite_le = ?
                       WHERE id = ? AND statut = 'a_traiter'""",
                    (paiement_id, par, quand, ligne_id))
                if curseur.rowcount != 1:
                    raise LookupError(ligne_id)

    def ignorer(self, ligne_id, motif, par, quand) -> None:
        with self.conn:
            self.conn.execute(
                """UPDATE releve_mm SET statut = 'ignore', paiement_id = NULL, motif = ?,
                          traite_par = ?, traite_le = ? WHERE id = ?""",
                (motif, par, quand, ligne_id))

    def defaire(self, ligne_id, par, quand) -> None:
        with self.conn:
            self.conn.execute(
                """UPDATE releve_mm SET statut = 'a_traiter', paiement_id = NULL, motif = NULL,
                          traite_par = ?, traite_le = ? WHERE id = ?""",
                (par, quand, ligne_id))