import re
import sqlite3
import tempfile
import unittest

from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.code_secours_repository import CodeSecoursRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services import audit_regles
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.codes_pdf import generer_codes_pdf
from edupaie.services.ecole import ParametresEcole
from edupaie.services.paiement_service import ErreurMetier

FORMAT_CODE = re.compile(r"[A-HJKMNP-Z2-9]{5}-[A-HJKMNP-Z2-9]{5}")


class TestRecuperation(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.utilisateurs = UtilisateurRepository(self.conn)
        self.auth = AuthService(self.utilisateurs, CodeSecoursRepository(self.conn))
        self.auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        self.auth.authentifier("admin", "Ecole2026")

    def tearDown(self):
        self.conn.close()

    def drapeau(self, login):
        return self.utilisateurs.get_by_login(login)["doit_changer_mdp"]

    # --- Mot de passe temporaire ----------------------------------------------------
    def test_le_premier_admin_choisit_son_mot_de_passe_sans_obligation(self):
        self.assertEqual(self.drapeau("admin"), 0)

    def test_mot_de_passe_temporaire_a_changer(self):
        self.auth.creer_utilisateur("jean", "Jean", "Temp2026", "comptable")
        self.assertEqual(self.drapeau("jean"), 1)
        self.auth.deconnecter()
        utilisateur = self.auth.authentifier("jean", "Temp2026")
        self.assertTrue(utilisateur["doit_changer_mdp"])
        for refuse in ("court", "Temp2026"):  # trop court / identique au temporaire
            with self.assertRaises(ErreurMetier):
                self.auth.definir_mon_mot_de_passe(refuse)
        self.auth.definir_mon_mot_de_passe("Perso2026")
        self.assertFalse(self.auth.utilisateur["doit_changer_mdp"])
        self.assertEqual(self.drapeau("jean"), 0)
        self.auth.deconnecter()
        self.assertIsNone(self.auth.authentifier("jean", "Temp2026"))
        self.assertFalse(self.auth.authentifier("jean", "Perso2026")["doit_changer_mdp"])
        with self.assertRaises(ErreurMetier):  # plus de changement obligatoire
            self.auth.definir_mon_mot_de_passe("Autre2026")

    def test_la_reinitialisation_par_l_admin_impose_un_nouveau_changement(self):
        self.auth.creer_utilisateur("jean", "Jean", "Temp2026", "comptable")
        identifiant = self.utilisateurs.get_by_login("jean")["id"]
        self.auth.deconnecter()
        self.auth.authentifier("jean", "Temp2026")
        self.auth.definir_mon_mot_de_passe("Perso2026")
        self.auth.deconnecter()
        self.auth.authentifier("admin", "Ecole2026")
        self.auth.reinitialiser_mot_de_passe(identifiant, "Autre2026")
        self.assertEqual(self.drapeau("jean"), 1)

    def test_un_changement_volontaire_efface_l_obligation(self):
        self.auth.creer_utilisateur("jean", "Jean", "Temp2026", "comptable")
        self.auth.deconnecter()
        self.auth.authentifier("jean", "Temp2026")
        self.auth.changer_mon_mot_de_passe("Temp2026", "Perso2026")
        self.assertEqual(self.drapeau("jean"), 0)

    # --- Codes de secours ---------------------------------------------------------------
    def test_generation_des_codes(self):
        with self.assertRaises(ErreurMetier):
            self.auth.generer_codes_secours("Mauvais123")
        codes = self.auth.generer_codes_secours("Ecole2026")
        self.assertEqual(len(codes), 8)
        self.assertEqual(len(set(codes)), 8)
        self.assertTrue(all(FORMAT_CODE.fullmatch(c) for c in codes))
        self.assertEqual(self.auth.codes_secours_restants(), 8)
        stocke = " ".join(r[0] for r in self.conn.execute("SELECT empreinte FROM code_secours"))
        for code in codes:  # seules les empreintes sont conservées
            self.assertNotIn(code.replace("-", ""), stocke)

    def test_les_codes_sont_reserves_aux_admins(self):
        self.auth.creer_utilisateur("jean", "Jean", "Temp2026", "comptable")
        self.auth.deconnecter()
        self.auth.authentifier("jean", "Temp2026")
        with self.assertRaises(ErreurMetier):
            self.auth.generer_codes_secours("Temp2026")
        self.assertEqual(self.auth.codes_secours_restants(), 0)

    def test_de_nouveaux_codes_remplacent_les_anciens(self):
        anciens = self.auth.generer_codes_secours("Ecole2026")
        nouveaux = self.auth.generer_codes_secours("Ecole2026")
        self.assertEqual(self.auth.codes_secours_restants(), 8)
        self.auth.deconnecter()
        with self.assertRaises(ErreurMetier):
            self.auth.reinitialiser_avec_code("admin", anciens[0], "NouveauMdp2026")
        self.assertEqual(self.auth.reinitialiser_avec_code(
            "admin", nouveaux[0], "NouveauMdp2026"), 7)

    # --- Récupération -------------------------------------------------------------------
    def test_recuperation_avec_un_code(self):
        codes = self.auth.generer_codes_secours("Ecole2026")
        self.auth.deconnecter()
        # minuscules, avec le tiret
        self.assertEqual(self.auth.reinitialiser_avec_code(
            "ADMIN", codes[0].lower(), "NouveauMdp2026"), 7)
        self.assertIsNone(self.auth.authentifier("admin", "Ecole2026"))
        self.assertIsNotNone(self.auth.authentifier("admin", "NouveauMdp2026"))
        self.assertFalse(self.auth.utilisateur["doit_changer_mdp"])
        with self.assertRaises(ErreurMetier):  # un code ne sert qu'une fois
            self.auth.reinitialiser_avec_code("admin", codes[0], "AutreMdp2026")
        # sans le tiret
        self.auth.reinitialiser_avec_code("admin", codes[1].replace("-", ""), "AutreMdp2026")
        self.assertIsNotNone(self.auth.authentifier("admin", "AutreMdp2026"))

    def test_recuperation_refusee(self):
        codes = self.auth.generer_codes_secours("Ecole2026")
        messages = set()
        for login, code in (("inconnu", codes[0]), ("admin", "AAAAA-AAAAA")):
            with self.assertRaises(ErreurMetier) as contexte:
                self.auth.reinitialiser_avec_code(login, code, "NouveauMdp2026")
            messages.add(str(contexte.exception))
        self.assertEqual(len(messages), 1)  # même message : on ne révèle pas si le compte existe
        with self.assertRaises(ErreurMetier):  # mot de passe trop faible
            self.auth.reinitialiser_avec_code("admin", codes[0], "faible")
        self.assertEqual(self.auth.codes_secours_restants(), 8)  # aucun code consommé

    def test_blocage_apres_cinq_tentatives(self):
        codes = self.auth.generer_codes_secours("Ecole2026")
        for _ in range(5):
            with self.assertRaises(ErreurMetier):
                self.auth.reinitialiser_avec_code("admin", "AAAAA-AAAAA", "NouveauMdp2026")
        with self.assertRaises(ErreurMetier) as contexte:
            self.auth.reinitialiser_avec_code("admin", codes[0], "NouveauMdp2026")
        self.assertIn("Trop", str(contexte.exception))

    def test_la_recuperation_debloque_un_compte_bloque(self):
        codes = self.auth.generer_codes_secours("Ecole2026")
        self.auth.deconnecter()
        for _ in range(5):
            self.assertIsNone(self.auth.authentifier("admin", "Mauvais123"))
        with self.assertRaises(ErreurMetier):
            self.auth.authentifier("admin", "Ecole2026")
        self.auth.reinitialiser_avec_code("admin", codes[0], "NouveauMdp2026")
        self.assertIsNotNone(self.auth.authentifier("admin", "NouveauMdp2026"))

    def test_un_compte_non_admin_n_a_pas_de_recuperation(self):
        self.auth.creer_utilisateur("jean", "Jean", "Temp2026", "comptable")
        codes = self.auth.generer_codes_secours("Ecole2026")
        with self.assertRaises(ErreurMetier):
            self.auth.reinitialiser_avec_code("jean", codes[0], "NouveauMdp2026")

    def test_nombre_d_admins(self):
        self.assertEqual(self.auth.nombre_admins(), 1)
        self.auth.creer_utilisateur("second", "Second", "Second2026", "admin")
        self.assertEqual(self.auth.nombre_admins(), 2)

    # --- Journal et PDF -------------------------------------------------------------------
    def test_la_recuperation_est_journalisee_sans_les_codes(self):
        journal = JournalService(JournalRepository(self.conn), self.auth)
        auth_ui = Audite(self.auth, journal, audit_regles.regles_auth())
        codes = auth_ui.generer_codes_secours("Ecole2026")
        auth_ui.deconnecter()
        with self.assertRaises(ErreurMetier):
            auth_ui.reinitialiser_avec_code("admin", "AAAAA-AAAAA", "NouveauMdp2026")
        auth_ui.reinitialiser_avec_code("admin", codes[0], "NouveauMdp2026")
        lignes = journal.repo.lister("2000-01-01", "2100-01-01")
        self.assertEqual([l["action"] for l in lignes],
                         ["utilisateur.recuperation", "utilisateur.recuperation_echec",
                          "utilisateur.codes_secours"])
        texte = " ".join(l["detail"] for l in lignes)
        for code in codes:
            self.assertNotIn(code, texte)
        self.assertNotIn("NouveauMdp2026", texte)

    def test_la_feuille_pdf_est_generee(self):
        codes = self.auth.generer_codes_secours("Ecole2026")
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_codes_pdf(
                codes, "Administrateur Œuvre", tmp, ParametresEcole("École test"))
            self.assertEqual(chemin.read_bytes()[:4], b"%PDF")


if __name__ == "__main__":
    unittest.main()