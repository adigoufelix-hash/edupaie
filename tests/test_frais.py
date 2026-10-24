import sqlite3
import unittest

from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.frais_service import FraisService
from edupaie.services.paiement_service import ErreurMetier

ANNEE = "2026-2027"


class TestFrais(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.service = FraisService(FraisRepository(self.conn))

    def test_total_de_plusieurs_lignes(self):
        self.service.ajouter_ligne("6e A", ANNEE, "Inscription", "20 000")
        self.service.ajouter_ligne("6e A", ANNEE, "Scolarité", 150000)
        self.assertEqual(self.service.total("6e A", ANNEE), 170000)

    def test_classe_sans_frais_vaut_zero(self):
        self.assertEqual(self.service.total("6e A", ANNEE), 0)

    def test_classes_et_annees_sont_separees(self):
        self.service.ajouter_ligne("6e A", ANNEE, "Scolarité", 100000)
        self.service.ajouter_ligne("6e B", ANNEE, "Scolarité", 120000)
        self.service.ajouter_ligne("6e A", "2027-2028", "Scolarité", 110000)
        self.assertEqual(self.service.total("6e A", ANNEE), 100000)
        self.assertEqual(self.service.total("6e B", ANNEE), 120000)
        self.assertEqual(self.service.total("6e A", "2027-2028"), 110000)

    def test_ligne_en_double_refusee_sans_tenir_compte_de_la_casse(self):
        self.service.ajouter_ligne("6e A", ANNEE, "Scolarité", 100000)
        with self.assertRaises(ErreurMetier):
            self.service.ajouter_ligne("6e A", ANNEE, "scolarité", 50000)

    def test_donnees_invalides_refusees(self):
        for libelle, montant in (("", 1000), ("Frais", "abc"),
                                 ("Frais", 0), ("Frais", -5)):
            with self.assertRaises(ErreurMetier):
                self.service.ajouter_ligne("6e A", ANNEE, libelle, montant)

    def test_modifier_et_supprimer(self):
        ligne_id = self.service.ajouter_ligne("6e A", ANNEE, "Examen", 10000)
        self.service.modifier_ligne(ligne_id, "Examens", "15000")
        self.assertEqual(self.service.total("6e A", ANNEE), 15000)
        self.service.supprimer_ligne(ligne_id)
        self.assertEqual(self.service.total("6e A", ANNEE), 0)

    def test_copie_vers_une_autre_classe_sans_ecraser(self):
        self.service.ajouter_ligne("6e A", ANNEE, "Inscription", 20000)
        self.service.ajouter_ligne("6e A", ANNEE, "Scolarité", 150000)
        self.service.ajouter_ligne("6e B", ANNEE, "Scolarité", 99000)
        copiees = self.service.copier("6e A", ANNEE, "6e B")
        self.assertEqual(copiees, 1)  # seule « Inscription » manquait
        self.assertEqual(self.service.total("6e B", ANNEE), 119000)

    def test_seul_un_admin_gere_les_frais(self):
        auth = AuthService(UtilisateurRepository(self.conn))
        auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        auth.authentifier("admin", "Ecole2026")
        auth.creer_utilisateur("caisse", "Caissier", "Caisse2026", "comptable")
        service = FraisService(FraisRepository(self.conn), auth)
        service.ajouter_ligne("6e A", ANNEE, "Scolarité", 100000)  # admin : autorisé
        auth.deconnecter()
        auth.authentifier("caisse", "Caisse2026")
        with self.assertRaises(ErreurMetier):
            service.ajouter_ligne("6e A", ANNEE, "Autre", 5000)
        self.assertEqual(service.total("6e A", ANNEE), 100000)  # lecture permise


if __name__ == "__main__":
    unittest.main()