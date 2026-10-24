import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.paiement_service import ErreurMetier, PaiementService


class TestAnnulation(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        self.eleves = EleveRepository(conn)
        self.paiements = PaiementRepository(conn)
        self.auth = AuthService(UtilisateurRepository(conn))
        self.auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        self.auth.authentifier("admin", "Ecole2026")
        self.auth.creer_utilisateur("caisse", "Caissier", "Caisse2026", "comptable")
        self.eleve = self.eleves.ajouter(
            Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        self.service = PaiementService(self.eleves, self.paiements, self.auth)
        self.p1 = self.service.enregistrer_paiement(
            self.eleve, 40000, "2026-09-01", "especes")
        self.p2 = self.service.enregistrer_paiement(
            self.eleve, 30000, "2026-09-02", "cheque")

    def test_annulation_recalcule_les_totaux_et_les_soldes(self):
        self.service.annuler_paiement(self.p1.id, "Montant saisi par erreur")
        sit = self.service.situation(self.eleve)
        self.assertEqual((sit.total_paye, sit.solde), (30000, 70000))
        self.assertEqual(self.paiements.obtenir(self.p2.id).solde_apres, 70000)

    def test_le_paiement_annule_reste_dans_l_historique(self):
        self.service.annuler_paiement(self.p1.id, "Montant saisi par erreur")
        historique = self.service.historique(self.eleve)
        self.assertEqual(len(historique), 2)
        annule = next(p for p in historique if p.id == self.p1.id)
        self.assertTrue(annule.annule)
        self.assertEqual(annule.motif_annulation, "Montant saisi par erreur")
        self.assertEqual(annule.annule_par, "Administrateur")
        self.assertIsNotNone(annule.annule_le)

    def test_double_annulation_refusee(self):
        self.service.annuler_paiement(self.p1.id, "Montant saisi par erreur")
        with self.assertRaises(ErreurMetier):
            self.service.annuler_paiement(self.p1.id, "Encore une fois")

    def test_motif_obligatoire(self):
        for motif in ("", "   ", "abc"):
            with self.assertRaises(ErreurMetier):
                self.service.annuler_paiement(self.p1.id, motif)
        self.assertFalse(self.paiements.obtenir(self.p1.id).annule)

    def test_seul_un_admin_peut_annuler(self):
        self.auth.deconnecter()
        self.auth.authentifier("caisse", "Caisse2026")
        self.assertFalse(self.service.peut_annuler())
        with self.assertRaises(ErreurMetier):
            self.service.annuler_paiement(self.p1.id, "Montant saisi par erreur")
        self.assertFalse(self.paiements.obtenir(self.p1.id).annule)

    def test_on_peut_encaisser_de_nouveau_apres_annulation(self):
        self.service.enregistrer_paiement(self.eleve, 30000, "2026-09-03", "especes")
        with self.assertRaises(ErreurMetier):  # déjà soldé
            self.service.enregistrer_paiement(self.eleve, 1000, "2026-09-04", "especes")
        self.service.annuler_paiement(self.p2.id, "Chèque sans provision")
        nouveau = self.service.enregistrer_paiement(
            self.eleve, 30000, "2026-09-05", "virement")
        self.assertEqual(nouveau.solde_apres, 0)

    def test_le_tableau_de_bord_ignore_les_paiements_annules(self):
        self.service.annuler_paiement(self.p2.id, "Chèque sans provision")
        self.assertEqual(self.service.tableau_de_bord()["total_encaisse"], 40000)
        derniers = [p.id for _, p in self.service.derniers_paiements(10)]
        self.assertNotIn(self.p2.id, derniers)


if __name__ == "__main__":
    unittest.main()