import sqlite3
import tempfile
import unittest
from pathlib import Path

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.caisse_service import CaisseService
from edupaie.services.cloture_pdf import generer_cloture_pdf
from edupaie.services.paiement_service import ErreurMetier, PaiementService


class TestCaisse(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        utilisateurs = UtilisateurRepository(conn)
        self.comptes = {
            "admin": (utilisateurs.creer("admin", "Administrateur", "x", "admin"),
                      "Administrateur", "admin"),
            "caisse": (utilisateurs.creer("caisse", "Caissier", "x", "comptable"),
                       "Caissier", "comptable"),
            "lecteur": (utilisateurs.creer("lecteur", "Lecteur", "x", "lecture"),
                        "Lecteur", "lecture"),
        }
        self.auth = AuthService(utilisateurs)
        self.eleves = EleveRepository(conn)
        self.paiements = PaiementRepository(conn)
        a = self.eleves.ajouter(Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        b = self.eleves.ajouter(Eleve(None, "B", "Deux", "6e B", "2026-2027", 50000))
        self.service = PaiementService(self.eleves, self.paiements, self.auth)
        self.caisse = CaisseService(self.paiements, self.auth)

        self.se_connecter("admin")
        self.service.enregistrer_paiement(a, 40000, "2026-09-01", "especes")
        self.service.enregistrer_paiement(a, 30000, "2026-09-02", "cheque")
        self.se_connecter("caisse")
        self.service.enregistrer_paiement(b, 20000, "2026-09-02", "mobile_money")
        erreur = self.service.enregistrer_paiement(b, 10000, "2026-09-03", "especes")
        self.se_connecter("admin")
        self.service.annuler_paiement(erreur.id, "Montant saisi par erreur")

    def se_connecter(self, nom):
        identifiant, nom_complet, role = self.comptes[nom]
        self.auth.utilisateur = {"id": identifiant, "login": nom,
                                 "nom_complet": nom_complet, "role": role}

    def test_totaux_de_l_admin_par_mode_et_par_caissier(self):
        c = self.caisse.cloture("2026-09-01", "2026-09-30")
        self.assertEqual((c["total"], c["nb"]), (90000, 3))
        self.assertEqual(c["par_mode"]["especes"], 40000)
        self.assertEqual(c["par_mode"]["cheque"], 30000)
        self.assertEqual(c["par_mode"]["mobile_money"], 20000)
        self.assertEqual(c["par_mode"]["virement"], 0)
        self.assertEqual([x["nom"] for x in c["caissiers"]], ["Administrateur", "Caissier"])
        self.assertEqual(c["caissiers"][0]["total"], 70000)

    def test_les_paiements_annules_sont_signales_mais_pas_comptes(self):
        c = self.caisse.cloture("2026-09-01", "2026-09-30")
        self.assertEqual((c["annules"]["nb"], c["annules"]["total"]), (1, 10000))

    def test_le_filtre_par_dates(self):
        c = self.caisse.cloture("2026-09-02", "2026-09-02")
        self.assertEqual((c["total"], c["nb"]), (50000, 2))
        c = self.caisse.cloture("2026-09-03", "2026-09-03")
        self.assertEqual(c["total"], 0)
        self.assertEqual(c["annules"]["nb"], 1)

    def test_un_comptable_ne_voit_que_ses_encaissements(self):
        self.se_connecter("caisse")
        c = self.caisse.cloture("2026-09-01", "2026-09-30")
        self.assertEqual((c["total"], c["nb"]), (20000, 1))
        self.assertEqual([x["nom"] for x in c["caissiers"]], ["Caissier"])
        self.assertIn("Caissier", c["portee"])

    def test_le_role_lecture_n_a_pas_acces(self):
        self.se_connecter("lecteur")
        with self.assertRaises(ErreurMetier):
            self.caisse.cloture("2026-09-01", "2026-09-30")

    def test_dates_invalides_refusees(self):
        with self.assertRaises(ErreurMetier):
            self.caisse.cloture("pas une date", "2026-09-30")
        with self.assertRaises(ErreurMetier):
            self.caisse.cloture("2026-09-30", "2026-09-01")

    def test_le_pdf_est_genere(self):
        c = self.caisse.cloture("2026-09-01", "2026-09-30")
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_cloture_pdf(c, tmp)
            self.assertTrue(chemin.exists())
            self.assertEqual(chemin.read_bytes()[:4], b"%PDF")

    def test_le_pdf_d_une_periode_vide_est_genere(self):
        c = self.caisse.cloture("2026-01-01", "2026-01-02")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(generer_cloture_pdf(c, tmp).exists())

    def test_le_pdf_supporte_les_noms_exotiques_et_plusieurs_pages(self):
        gros = self.eleves.ajouter(Eleve(None, "Nguyễn", "Đức", "6e A", "2026-2027", 1000000))
        self.se_connecter("admin")
        for _ in range(60):
            self.service.enregistrer_paiement(gros, 1000, "2026-09-04", "especes")
        c = self.caisse.cloture("2026-09-01", "2026-09-30")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(generer_cloture_pdf(c, Path(tmp)).exists())


if __name__ == "__main__":
    unittest.main()