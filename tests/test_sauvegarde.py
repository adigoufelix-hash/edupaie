import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.sauvegarde_service import SauvegardeService


class TestSauvegarde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        racine = Path(self.tmp.name)
        self.base = racine / "edupaie.db"
        conn = sqlite3.connect(self.base)
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO eleve (nom, prenom, classe, annee_scolaire, total_du) "
                     "VALUES ('A', 'Un', '6e A', '2026-2027', 1000)")
        conn.commit()
        conn.close()
        self.service = SauvegardeService(
            chemin_base=self.base, dossier=racine / "sauvegardes", garder=3)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _nb_eleves(chemin):
        conn = sqlite3.connect(chemin)
        try:
            return conn.execute("SELECT COUNT(*) FROM eleve").fetchone()[0]
        finally:
            conn.close()

    def _modifier_base(self, sql):
        conn = sqlite3.connect(self.base)
        conn.execute(sql)
        conn.commit()
        conn.close()

    def test_la_copie_est_lisible(self):
        copie = self.service.sauvegarder()
        self.assertEqual(self._nb_eleves(copie), 1)

    def test_la_purge_ne_garde_que_les_plus_recentes(self):
        for i in range(5):
            self.service.sauvegarder(f"t{i}")
        motifs = {s["motif"] for s in self.service.lister()}
        self.assertEqual(motifs, {"t2", "t3", "t4"})

    def test_sauvegarde_auto_ignoree_si_rien_n_a_change(self):
        self.assertIsNotNone(self.service.sauvegarde_auto())
        self.assertIsNone(self.service.sauvegarde_auto())
        time.sleep(1.1)
        self._modifier_base("DELETE FROM eleve")
        self.assertIsNotNone(self.service.sauvegarde_auto())

    def test_restauration_recupere_les_donnees(self):
        copie = self.service.sauvegarder()
        self._modifier_base("DELETE FROM eleve")
        self.assertEqual(self._nb_eleves(self.base), 0)
        self.service.restaurer(copie)
        self.assertEqual(self._nb_eleves(self.base), 1)
        self.assertTrue(any(s["motif"] == "avant-restauration"
                            for s in self.service.lister()))

    def test_restauration_refuse_un_fichier_invalide(self):
        faux = Path(self.tmp.name) / "faux.db"
        faux.write_text("ceci n'est pas une base", encoding="utf-8")
        with self.assertRaises(ErreurMetier):
            self.service.restaurer(faux)
        self.assertEqual(self._nb_eleves(self.base), 1)

    def test_seul_un_admin_gere_les_sauvegardes(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        auth = AuthService(UtilisateurRepository(conn))
        auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        auth.authentifier("admin", "Ecole2026")
        auth.creer_utilisateur("caisse", "Caissier", "Caisse2026", "comptable")
        service = SauvegardeService(auth, self.base, self.service.dossier)
        copie = service.sauvegarder()  # admin : autorisé
        auth.deconnecter()
        auth.authentifier("caisse", "Caisse2026")
        with self.assertRaises(ErreurMetier):
            service.sauvegarder()
        with self.assertRaises(ErreurMetier):
            service.restaurer(copie)
        service.sauvegarde_auto()  # automatique : jamais bloquée par les droits


if __name__ == "__main__":
    unittest.main()