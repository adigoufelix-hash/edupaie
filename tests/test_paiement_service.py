import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.services.paiement_service import PaiementService, ErreurMetier


class TestPaiementService(unittest.TestCase):
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

    def test_non_paye_au_depart(self):
        s = self.service.situation(self.eid)
        self.assertEqual((s.total_paye, s.solde, s.statut), (0, 100000, "Non payé"))

    def test_partiel_puis_solde(self):
        p = self.service.enregistrer_paiement(self.eid, 40000, "2026-09-01", "especes")
        self.assertEqual(p.solde_apres, 60000)
        self.assertTrue(p.numero_recu.startswith("REC-2026-"))
        self.assertEqual(self.service.situation(self.eid).statut, "Partiellement payé")
        self.service.enregistrer_paiement(self.eid, 60000, "2026-09-02", "virement")
        self.assertEqual(self.service.situation(self.eid).statut, "Soldé")

    def test_refus_depassement_du_solde(self):
        with self.assertRaises(ErreurMetier):
            self.service.enregistrer_paiement(self.eid, 100001, "2026-09-01", "especes")

    def test_refus_donnees_invalides(self):
        cas = [("abc", "2026-09-01", "especes"), (-5, "2026-09-01", "especes"),
               (1000, "31/12/2026", "especes"), (1000, "2099-01-01", "especes"),
               (1000, "2026-09-01", "carte")]
        for montant, dt, mode in cas:
            with self.subTest(montant=montant, date=dt, mode=mode):
                with self.assertRaises(ErreurMetier):
                    self.service.enregistrer_paiement(self.eid, montant, dt, mode)


if __name__ == "__main__":
    unittest.main()