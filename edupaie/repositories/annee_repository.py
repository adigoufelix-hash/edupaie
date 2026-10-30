import sqlite3
from datetime import date

from edupaie.repositories.paiement_repository import PaiementRepository


def decaler_date(iso: str, annees: int) -> str:
    """Même jour, `annees` plus tard (le 29 février devient le 28)."""
    d = date.fromisoformat(iso)
    try:
        return d.replace(year=d.year + annees).isoformat()
    except ValueError:
        return d.replace(year=d.year + annees, day=28).isoformat()


class AnneeRepository:
    """Accès aux données des années scolaires. Aucune règle métier ici."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --- Paramètres (année active) -----------------------------------------------
    def get_parametre(self, cle: str):
        ligne = self.conn.execute(
            "SELECT valeur FROM parametre WHERE cle = ?", (cle,)).fetchone()
        return ligne["valeur"] if ligne else None

    def _ecrire_parametre(self, cle: str, valeur: str) -> None:
        self.conn.execute(
            "INSERT INTO parametre (cle, valeur) VALUES (?, ?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, valeur))

    def set_parametre(self, cle: str, valeur: str) -> None:
        with self.conn:
            self._ecrire_parametre(cle, valeur)

    # --- Lecture ------------------------------------------------------------------------
    def annees(self) -> list[str]:
        lignes = self.conn.execute(
            "SELECT annee_scolaire FROM eleve UNION SELECT annee_scolaire FROM frais_classe "
            "UNION SELECT annee_scolaire FROM echeance").fetchall()
        return sorted(r[0] for r in lignes if r[0])

    def eleves_avec_solde(self, annee: str):
        """Élèves de l'année avec ce qu'ils ont payé et le total de leurs remises."""
        return self.conn.execute(
            """SELECT e.id, e.nom, e.prenom, e.classe, e.total_du,
                      COALESCE((SELECT SUM(r.montant) FROM remise r
                                WHERE r.eleve_id = e.id AND r.annule = 0), 0) AS remises,
                      COALESCE((SELECT SUM(p.montant) FROM paiement p
                                WHERE p.eleve_id = e.id AND p.annule = 0), 0) AS paye
               FROM eleve e WHERE e.annee_scolaire = ?
               ORDER BY e.classe, e.nom, e.prenom""", (annee,)).fetchall()

    def deja_passes(self, annee_cible: str) -> set[int]:
        return {r[0] for r in self.conn.execute(
            "SELECT eleve_ancien_id FROM passage WHERE annee_cible = ?", (annee_cible,))}

    def inscrits(self, annee: str) -> set[tuple]:
        return {(r[0].casefold(), r[1].casefold()) for r in self.conn.execute(
            "SELECT nom, prenom FROM eleve WHERE annee_scolaire = ?", (annee,))}

    def total_frais(self, classe: str, annee: str) -> int:
        return self.conn.execute(
            "SELECT COALESCE(SUM(montant), 0) FROM frais_classe "
            "WHERE classe = ? COLLATE NOCASE AND annee_scolaire = ?",
            (classe, annee)).fetchone()[0]

    # --- Écriture -------------------------------------------------------------------------
    def executer_lot(self, lignes, annee_source, annee_cible, auteur, quand) -> None:
        """Réinscrit tous les élèves en une seule transaction : tout ou rien."""
        paiements = PaiementRepository(self.conn)
        with self.conn:
            for l in lignes:
                cur = self.conn.execute(
                    "INSERT INTO eleve (nom, prenom, classe, annee_scolaire, total_du) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (l["nom"], l["prenom"], l["classe_cible"], annee_cible, l["total"]))
                nouveau_id = cur.lastrowid
                contact = self.conn.execute(
                    "SELECT tuteur, telephone FROM contact_eleve WHERE eleve_id = ?",
                    (l["eleve_id"],)).fetchone()
                if contact:
                    self.conn.execute(
                        "INSERT INTO contact_eleve (eleve_id, tuteur, telephone) "
                        "VALUES (?, ?, ?)",
                        (nouveau_id, contact["tuteur"], contact["telephone"]))
                self.conn.execute(
                    "INSERT INTO passage (eleve_ancien_id, eleve_nouveau_id, annee_source, "
                    "annee_cible, classe_source, classe_cible, arrieres, fait_le, fait_par) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (l["eleve_id"], nouveau_id, annee_source, annee_cible,
                     l["classe_source"], l["classe_cible"], l["arrieres"], quand, auteur))
                if l["arrieres"] > 0:  # l'ancienne fiche est soldée par un report visible
                    self.conn.execute(
                        "INSERT INTO remise (eleve_id, type, valeur, montant, motif, "
                        "accorde_par, accorde_le) VALUES (?, 'montant', ?, ?, ?, ?, ?)",
                        (l["eleve_id"], l["arrieres"], l["arrieres"],
                         f"Arriéré reporté sur l'année {annee_cible}", auteur, quand))
                    paiements._recalculer_soldes(l["eleve_id"])
            self._ecrire_parametre("annee_active", annee_cible)

    def copier_frais_et_echeances(self, source: str, cible: str) -> dict:
        """Reprend les frais et l'échéancier des classes qui n'ont encore rien pour `cible`."""
        decalage = int(cible[:4]) - int(source[:4])
        resultat = {"frais_classes": 0, "frais_lignes": 0,
                    "echeance_classes": 0, "echeance_lignes": 0}
        with self.conn:
            for (classe,) in self.conn.execute(
                    "SELECT DISTINCT classe FROM frais_classe WHERE annee_scolaire = ?",
                    (source,)).fetchall():
                if self.conn.execute(
                        "SELECT COUNT(*) FROM frais_classe WHERE classe = ? "
                        "AND annee_scolaire = ?", (classe, cible)).fetchone()[0]:
                    continue
                lignes = self.conn.execute(
                    "SELECT libelle, montant FROM frais_classe WHERE classe = ? "
                    "AND annee_scolaire = ? ORDER BY id", (classe, source)).fetchall()
                for l in lignes:
                    self.conn.execute(
                        "INSERT INTO frais_classe (classe, annee_scolaire, libelle, montant) "
                        "VALUES (?, ?, ?, ?)", (classe, cible, l["libelle"], l["montant"]))
                resultat["frais_classes"] += 1
                resultat["frais_lignes"] += len(lignes)
            for (classe,) in self.conn.execute(
                    "SELECT DISTINCT classe FROM echeance WHERE annee_scolaire = ?",
                    (source,)).fetchall():
                if self.conn.execute(
                        "SELECT COUNT(*) FROM echeance WHERE classe = ? "
                        "AND annee_scolaire = ?", (classe, cible)).fetchone()[0]:
                    continue
                lignes = self.conn.execute(
                    "SELECT libelle, date_limite, pourcentage FROM echeance WHERE classe = ? "
                    "AND annee_scolaire = ? ORDER BY date_limite, id",
                    (classe, source)).fetchall()
                for l in lignes:
                    self.conn.execute(
                        "INSERT INTO echeance (classe, annee_scolaire, libelle, date_limite, "
                        "pourcentage) VALUES (?, ?, ?, ?, ?)",
                        (classe, cible, l["libelle"],
                         decaler_date(l["date_limite"], decalage), l["pourcentage"]))
                resultat["echeance_classes"] += 1
                resultat["echeance_lignes"] += len(lignes)
        return resultat