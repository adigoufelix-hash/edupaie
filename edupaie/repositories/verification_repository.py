import sqlite3


class VerificationRepository:
    """Accès aux données de vérification des reçus. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def trouver_recu(self, numero: str):
        return self.conn.execute(
            """SELECT p.id, p.numero_recu, p.montant, p.date_paiement, p.mode, p.eleve_id,
                      p.encaisse_par, p.annule, p.motif_annulation, p.annule_par,
                      p.annule_le, e.nom, e.prenom, e.classe
               FROM paiement p JOIN eleve e ON e.id = p.eleve_id
               WHERE p.numero_recu = ?""", (numero,)).fetchone()

    def get_parametre(self, cle: str):
        ligne = self.conn.execute(
            "SELECT valeur FROM parametre WHERE cle = ?", (cle,)).fetchone()
        return ligne["valeur"] if ligne else None

    def set_parametre(self, cle: str, valeur: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO parametre (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, valeur))