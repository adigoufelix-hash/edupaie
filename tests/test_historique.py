import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.services.paiement_service import PaiementService, ErreurMetier


class TestHistorique(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        eleves = EleveRepository(conn)
        self.eid = eleves.ajouter(
            Eleve(None, "Test", "Jean", "6e A", "2026-2027", 100000))
        self.service = PaiementService(eleves, PaiementRepository(conn))

    def test_historique_chronologique(self):
        self.service.enregistrer_paiement(self.eid, 20000, "2026-09-05", "especes")
        self.service.enregistrer_paiement(self.eid, 30000, "2026-09-01", "cheque")
        montants = [p.montant for p in self.service.historique(self.eid)]
        self.assertEqual(montants, [30000, 20000])

    def test_reconsulter_un_recu(self):
        p = self.service.enregistrer_paiement(self.eid, 30000, "2026-09-01", "especes")
        eleve, recu = self.service.recu(p.id)
        self.assertEqual(eleve.nom, "Test")
        self.assertEqual(recu.numero_recu, p.numero_recu)
        self.assertEqual(recu.solde_apres, 70000)

    def test_recu_inexistant(self):
        with self.assertRaises(ErreurMetier):
            self.service.recu(9999)


if __name__ == "__main__":
    unittest.main()