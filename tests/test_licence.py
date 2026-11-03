import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from edupaie.permissions import a_permission
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.parametre_repository import ParametreRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services import audit_regles
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.licence import construire_cle, identifiant_machine, lire_cle
from edupaie.services.licence_service import LicenceService, MarquesMemoire
from edupaie.services.paiement_service import ErreurMetier
from outils.licences import (charger_cle_privee, emettre, enregistrer, generer_paire,
                             prochain_numero)

JOUR0 = date(2026, 11, 1)
MACHINE = identifiant_machine("guid-de-test")


class Horloge:
    def __init__(self, jour):
        self.jour = jour

    def __call__(self):
        return self.jour


class TestLicence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pem, cls.publique = generer_paire()
        cls.cle_privee = charger_cle_privee(pem)
        pem, cls.autre_publique = generer_paire()
        cls.autre_cle = charger_cle_privee(pem)

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.parametres = ParametreRepository(self.conn)
        self.marques = MarquesMemoire()
        self.horloge = Horloge(JOUR0)
        self.service = self.creer()

    def tearDown(self):
        self.conn.close()

    def creer(self, auth=None, machine=MACHINE, publique=None):
        return LicenceService(
            self.parametres, cle_publique_hex=self.publique if publique is None else publique,
            marques=self.marques, machine=machine, aujourdhui=self.horloge, auth=auth)

    def avancer(self, jours):
        self.horloge.jour = JOUR0 + timedelta(days=jours)
        return self.creer().etat()

    def cle(self, machine=MACHINE, expire=None, ecole="Collège Test", numero="LIC-0001",
            prive=None):
        return emettre(prive or self.cle_privee, ecole, machine, expire, numero, emise=JOUR0)

    # --- Période d'essai ---------------------------------------------------------------
    def test_periode_d_essai(self):
        etat = self.service.etat()
        self.assertEqual((etat.mode, etat.jours_restants), ("essai", 30))
        for jours, restants in ((10, 20), (29, 1)):
            etat = self.avancer(jours)
            self.assertEqual((etat.mode, etat.jours_restants), ("essai", restants))
        etat = self.avancer(30)
        self.assertEqual(etat.mode, "expire")
        self.assertTrue(etat.restreint)

    def test_reculer_l_horloge_ne_rallonge_pas_l_essai(self):
        self.service.etat()
        self.assertEqual(self.avancer(20).jours_restants, 10)
        etat = self.avancer(5)
        self.assertEqual((etat.mode, etat.jours_restants), ("essai", 10))
        self.assertIn("date", etat.avertissement)

    def test_une_erreur_d_horloge_en_avant_n_est_pas_definitive(self):
        self.service.etat()
        self.assertEqual(self.avancer(500).mode, "expire")
        etat = self.avancer(10)
        self.assertEqual((etat.mode, etat.jours_restants), ("essai", 20))

    def test_effacer_la_base_ne_relance_pas_l_essai(self):
        self.service.etat()
        self.avancer(10)
        self.conn.execute("DELETE FROM parametre")
        self.conn.commit()
        etat = self.creer().etat()
        self.assertEqual((etat.mode, etat.jours_restants), ("essai", 20))
        self.assertEqual(self.parametres.get("essai_debut"), JOUR0.isoformat())

    def test_une_marque_alteree_termine_l_essai(self):
        self.service.etat()
        self.marques.valeurs["essai_debut"] = "2020-01-01:000000000000"
        etat = self.creer().etat()
        self.assertEqual(etat.mode, "expire")
        self.assertIn("altér", etat.message)

    # --- Activation ----------------------------------------------------------------------
    def test_activation_d_une_licence(self):
        etat = self.service.activer(self.cle())
        self.assertEqual((etat.mode, etat.ecole, etat.licence_id, etat.expire_le),
                         ("licence", "Collège Test", "LIC-0001", None))
        self.assertIsNone(etat.avertissement)
        self.assertEqual(self.creer().etat().mode, "licence")  # conservée dans la base
        self.assertEqual(self.avancer(400).mode, "licence")    # bien après l'essai

    def test_la_cle_collee_avec_des_retours_a_la_ligne_est_acceptee(self):
        cle = self.cle()
        coupee = "\n".join(cle[i:i + 60] for i in range(0, len(cle), 60))
        self.assertEqual(self.service.activer("  " + coupee + "\n").mode, "licence")

    def test_licences_refusees(self):
        payload, signature = lire_cle(self.cle())
        donnees = json.loads(payload)
        donnees["expire"] = "2099-01-01"
        modifiee = construire_cle(json.dumps(
            donnees, separators=(",", ":"), sort_keys=True).encode("utf-8"), signature)
        for texte in (modifiee, self.cle(prive=self.autre_cle), "n'importe quoi", "",
                      "EDUPAIE1.abc.def"):
            with self.assertRaises(ErreurMetier):
                self.service.activer(texte)
        self.assertIsNone(self.parametres.get("licence"))
        self.assertEqual(self.service.etat().mode, "essai")

    def test_licence_liee_a_un_ordinateur(self):
        with self.assertRaises(ErreurMetier) as contexte:
            self.service.activer(self.cle(machine=identifiant_machine("autre-pc")))
        self.assertIn("ordinateur", str(contexte.exception))
        self.service.activer(self.cle(machine="*"))  # valable partout
        autre = self.creer(machine=identifiant_machine("autre-pc"))
        self.assertEqual(autre.etat().mode, "licence")

    def test_sans_cle_publique_aucune_licence_n_est_acceptee(self):
        service = self.creer(publique="")
        self.assertFalse(service.configuree())
        with self.assertRaises(ErreurMetier):
            service.activer(self.cle())

    # --- Expiration ------------------------------------------------------------------------
    def test_expiration_et_avertissement(self):
        self.service.activer(self.cle(expire=date(2026, 12, 1)))
        etat = self.service.etat()
        self.assertEqual((etat.mode, etat.jours_restants), ("licence", 30))
        self.assertIn("30 jour", etat.avertissement)
        self.horloge.jour = date(2026, 12, 1)  # le dernier jour compte encore
        etat = self.creer().etat()
        self.assertEqual((etat.mode, etat.jours_restants), ("licence", 0))
        self.assertIn("aujourd'hui", etat.avertissement)
        self.horloge.jour = date(2026, 12, 2)
        etat = self.creer().etat()
        self.assertEqual(etat.mode, "expire")
        self.assertIn("expirée", etat.message)
        self.assertTrue(etat.restreint)

    def test_on_ne_peut_pas_activer_une_licence_deja_expiree(self):
        self.horloge.jour = date(2026, 12, 5)
        with self.assertRaises(ErreurMetier) as contexte:
            self.creer().activer(self.cle(expire=date(2026, 12, 1)))
        self.assertIn("expirée", str(contexte.exception))

    def test_reculer_l_horloge_ne_ressuscite_pas_une_licence_expiree(self):
        self.service.activer(self.cle(expire=date(2026, 12, 1)))
        self.assertEqual(self.avancer(39).mode, "expire")   # 10 décembre
        self.assertEqual(self.avancer(14).mode, "expire")   # horloge remise au 15 novembre

    def test_licence_sans_limite_de_duree(self):
        self.service.activer(self.cle())
        self.horloge.jour = date(2030, 1, 1)
        etat = self.creer().etat()
        self.assertEqual(etat.mode, "licence")
        self.assertIsNone(etat.avertissement)

    # --- Droits, mode consultation, journal ----------------------------------------------------
    def test_seul_un_admin_active_une_licence(self):
        class FauxAuth:
            def __init__(self, role):
                self.role = role

            def peut(self, permission):
                return a_permission(self.role, permission)

        with self.assertRaises(ErreurMetier):
            self.creer(auth=FauxAuth("comptable")).activer(self.cle())
        self.assertEqual(self.creer(auth=FauxAuth("admin")).activer(self.cle()).mode,
                         "licence")

    def test_mode_consultation(self):
        auth = AuthService(UtilisateurRepository(self.conn))
        auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        auth.authentifier("admin", "Ecole2026")
        auth.creer_utilisateur("caisse", "Caissier", "Caisse2026", "comptable")
        auth.restriction = lambda: True
        auth.deconnecter()
        auth.authentifier("admin", "Ecole2026")
        for permission in ("eleve.lire", "paiement.lire", "sauvegarde.gerer",
                           "licence.gerer", "audit.voir"):
            self.assertTrue(auth.peut(permission), permission)
        for permission in ("paiement.encaisser", "eleve.ecrire", "utilisateur.gerer",
                           "remise.gerer", "annee.gerer"):
            self.assertFalse(auth.peut(permission), permission)
        auth.deconnecter()
        auth.authentifier("caisse", "Caisse2026")
        self.assertTrue(auth.peut("paiement.lire"))
        self.assertFalse(auth.peut("paiement.encaisser"))
        self.assertFalse(auth.peut("licence.gerer"))
        auth.restriction = lambda: False  # licence activée : effet à la connexion suivante
        auth.deconnecter()
        auth.authentifier("caisse", "Caisse2026")
        self.assertTrue(auth.peut("paiement.encaisser"))
        auth.restriction = lambda: True   # la session en cours ne change pas
        self.assertTrue(auth.peut("paiement.encaisser"))

    def test_journal_de_la_licence(self):
        journal = JournalService(JournalRepository(self.conn))
        service = Audite(self.service, journal, audit_regles.regles_licence())
        service.activer(self.cle())
        with self.assertRaises(ErreurMetier):
            service.activer("n'importe quoi")
        lignes = journal.repo.lister("2000-01-01", "2100-01-01")
        self.assertEqual([l["action"] for l in lignes],
                         ["licence.echec", "licence.activation"])
        self.assertIn("LIC-0001", lignes[1]["detail"])
        for ligne in lignes:  # la clé n'est jamais écrite dans le journal
            self.assertNotIn("EDUPAIE1", ligne["detail"])

    # --- Identifiant de l'ordinateur et outils du fournisseur ------------------------------------
    def test_identifiant_de_l_ordinateur(self):
        self.assertRegex(MACHINE, r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")
        self.assertEqual(identifiant_machine("a"), identifiant_machine("a"))
        self.assertNotEqual(identifiant_machine("a"), identifiant_machine("b"))

    def test_outils_du_fournisseur(self):
        with tempfile.TemporaryDirectory() as tmp:
            registre = Path(tmp) / "registre.csv"
            self.assertEqual(prochain_numero(registre), "LIC-0001")
            enregistrer(registre, "LIC-0001", "Collège Test", MACHINE, None, JOUR0)
            self.assertEqual(prochain_numero(registre), "LIC-0002")
            self.assertIn("Collège Test", registre.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            emettre(self.cle_privee, "École", "pas-une-machine", None, "LIC-0001")
        with self.assertRaises(ValueError):
            emettre(self.cle_privee, "   ", MACHINE, None, "LIC-0001")
        self.assertEqual(len(self.publique), 64)


if __name__ == "__main__":
    unittest.main()