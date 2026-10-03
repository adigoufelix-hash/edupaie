import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.services.paiement_service import PaiementService


class TestDashboard(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        eleves = EleveRepository(conn)
        self.a = eleves.ajouter(Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        self.b = eleves.ajouter(Eleve(None, "B", "Deux", "6e A", "2026-2027", 50000))
        self.c = eleves.ajouter(Eleve(None, "C", "Trois", "6e B", "2026-2027", 80000))
        self.service = PaiementService(eleves, PaiementRepository(conn))

    def test_chiffres_cles(self):
        self.service.enregistrer_paiement(self.a, 100000, "2026-09-01", "especes")
        self.service.enregistrer_paiement(self.b, 20000, "2026-09-02", "cheque")
        d = self.service.tableau_de_bord()
        self.assertEqual(d["nb_eleves"], 3)
        self.assertEqual(d["total_encaisse"], 120000)
        self.assertEqual(d["total_restant"], 110000)
        self.assertEqual(d["nb_non_soldes"], 2)

    def test_derniers_et_repartition(self):
        self.service.enregistrer_paiement(self.a, 100000, "2026-09-01", "especes")
        self.service.enregistrer_paiement(self.b, 20000, "2026-09-02", "cheque")
        dernier_eleve, dernier_paiement = self.service.derniers_paiements(1)[0]
        self.assertEqual((dernier_eleve.nom, dernier_paiement.montant), ("B", 20000))
        d = self.service.tableau_de_bord()
        self.assertEqual((d["nb_soldes"], d["nb_partiels"], d["nb_non_payes"]), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()