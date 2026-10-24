import sqlite3
import unittest

from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.paiement_service import ErreurMetier


class TestAuthService(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        self.auth = AuthService(UtilisateurRepository(conn))
        self.auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        self.assertIsNotNone(self.auth.authentifier("admin", "Ecole2026"))

    def test_le_premier_compte_est_toujours_admin(self):
        auth = AuthService(UtilisateurRepository(self._base_vide()))
        auth.creer_utilisateur("premier", "Premier", "Ecole2026", "lecture")
        self.assertEqual(auth.authentifier("premier", "Ecole2026")["role"], "admin")

    def test_connexion_valide_renvoie_l_utilisateur(self):
        self.auth.deconnecter()
        utilisateur = self.auth.authentifier("admin", "Ecole2026")
        self.assertIsNotNone(utilisateur)
        self.assertEqual(utilisateur["login"], "admin")
        self.assertEqual(self.auth.utilisateur, utilisateur)

    def test_login_insensible_a_la_casse(self):
        self.assertIsNotNone(self.auth.authentifier("ADMIN", "Ecole2026"))

    def test_mauvais_mot_de_passe_refuse(self):
        self.auth.deconnecter()
        self.assertIsNone(self.auth.authentifier("admin", "Mauvais123"))
        self.assertIsNone(self.auth.utilisateur)

    def test_login_inconnu_refuse(self):
        self.assertIsNone(self.auth.authentifier("inconnu", "Ecole2026"))

    def test_blocage_apres_cinq_echecs(self):
        self.auth.deconnecter()
        for _ in range(5):
            self.assertIsNone(self.auth.authentifier("admin", "Mauvais123"))
        with self.assertRaises(ErreurMetier):
            self.auth.authentifier("admin", "Ecole2026")  # même avec le bon mot de passe

    def test_seul_un_admin_peut_creer_un_compte(self):
        self.auth.creer_utilisateur("caisse", "Caissier", "Caisse2026", "comptable")
        self.auth.deconnecter()
        self.auth.authentifier("caisse", "Caisse2026")
        with self.assertRaises(ErreurMetier):
            self.auth.creer_utilisateur("autre", "Autre", "Autre2026", "lecture")

    def test_login_en_double_refuse(self):
        with self.assertRaises(ErreurMetier):
            self.auth.creer_utilisateur("admin", "Double", "Ecole2026", "lecture")

    def test_role_inconnu_refuse(self):
        with self.assertRaises(ErreurMetier):
            self.auth.creer_utilisateur("x", "X", "Ecole2026", "superchef")

    def test_mot_de_passe_trop_faible_refuse(self):
        with self.assertRaises(ErreurMetier):
            self.auth.creer_utilisateur("x", "X", "court", "lecture")

    def test_permissions_selon_le_role(self):
        self.assertTrue(self.auth.peut("utilisateur.gerer"))
        self.auth.creer_utilisateur("lecteur", "Lecteur", "Lecture2026", "lecture")
        self.auth.deconnecter()
        self.auth.authentifier("lecteur", "Lecture2026")
        self.assertTrue(self.auth.peut("eleve.lire"))
        self.assertFalse(self.auth.peut("paiement.encaisser"))
        with self.assertRaises(ErreurMetier):
            self.auth.lister_utilisateurs()

    def test_impossible_de_supprimer_son_propre_compte(self):
        with self.assertRaises(ErreurMetier):
            self.auth.supprimer_utilisateur(self.auth.utilisateur["id"])

    def test_changer_son_mot_de_passe(self):
        with self.assertRaises(ErreurMetier):
            self.auth.changer_mon_mot_de_passe("Faux12345", "Nouveau2026")
        self.auth.changer_mon_mot_de_passe("Ecole2026", "Nouveau2026")
        self.auth.deconnecter()
        self.assertIsNone(self.auth.authentifier("admin", "Ecole2026"))
        self.assertIsNotNone(self.auth.authentifier("admin", "Nouveau2026"))

    @staticmethod
    def _base_vide():
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        return conn


if __name__ == "__main__":
    unittest.main()