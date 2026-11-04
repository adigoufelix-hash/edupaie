import sqlite3
import unittest
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import unquote

from edupaie.models.entities import Eleve
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.repositories.resume_repository import ResumeRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services import audit_regles
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.caisse_service import CaisseService
from edupaie.services.ecole import ParametresEcole
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.resume_service import ResumeJourService

JOUR = "2026-11-02"
ECOLE = ParametresEcole("Collège Test")
MAINTENANT = datetime(2026, 11, 2, 17, 42)


class TestResume(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        utilisateurs = UtilisateurRepository(self.conn)
        self.auth = AuthService(utilisateurs)
        self.comptes = {}
        for login, nom, role in (("admin", "Administrateur", "admin"),
                                 ("kossi", "Kossi Mensah", "comptable"),
                                 ("ama", "Ama Dosseh", "comptable"),
                                 ("lecteur", "Lecteur", "lecture")):
            self.comptes[login] = {"id": utilisateurs.creer(login, nom, "x", role),
                                   "login": login, "nom_complet": nom, "role": role}
        eleves = EleveRepository(self.conn)
        paiements = PaiementRepository(self.conn)
        self.remises = RemiseRepository(self.conn)
        paie = PaiementService(eleves, paiements, self.auth)
        eleve = eleves.ajouter(Eleve(None, "Kouassi", "Kofi", "6e A", "2026-2027", 200000))

        self.se_connecter("kossi")
        paie.enregistrer_paiement(eleve, 40000, JOUR, "especes")
        annule = paie.enregistrer_paiement(eleve, 20000, JOUR, "mobile_money")
        self.se_connecter("ama")
        paie.enregistrer_paiement(eleve, 10000, JOUR, "cheque")
        self.se_connecter("admin")
        paie.annuler_paiement(annule.id, "Montant erroné")
        self.remises.ajouter(eleve, "montant", 20000, 20000, "Bourse", "Administrateur",
                             f"{JOUR}T10:00:00")
        self.remises.ajouter(eleve, "montant", 5000, 5000, "Fratrie", "Administrateur",
                             "2026-11-03T09:00:00")  # un autre jour : exclue
        retiree = self.remises.ajouter(eleve, "montant", 7000, 7000, "Doublon",
                                       "Administrateur", f"{JOUR}T11:00:00")
        self.remises.annuler(retiree, "Erreur", "Administrateur", f"{JOUR}T12:00:00")

        self.service = ResumeJourService(
            CaisseService(paiements, self.auth), ResumeRepository(self.conn), self.auth,
            ecole=lambda: ECOLE, maintenant=lambda: MAINTENANT)

    def tearDown(self):
        self.conn.close()

    def se_connecter(self, login):
        self.auth.utilisateur = dict(self.comptes[login])

    # --- Le message ----------------------------------------------------------------------
    def test_message_de_l_administrateur(self):
        m = self.service.message(JOUR, JOUR)
        for attendu in (
                "*Collège Test*", "Résumé de caisse - 02/11/2026", "Tous les caissiers",
                "*Total encaissé : 50 000 FCFA* (2 paiements)",
                "- Espèces : 40 000 FCFA", "- Chèque : 10 000 FCFA",
                "- Kossi Mensah : 1 paiement, 40 000 FCFA",
                "- Ama Dosseh : 1 paiement, 10 000 FCFA",
                "*Paiements annulés : 1* (20 000 FCFA non comptés)", "REC-2026-", "Montant erroné",
                "*Remises accordées : 1* (20 000 FCFA)",
                "Kouassi Kofi (6e A) : 20 000 FCFA - Bourse",
                "Envoyé par Administrateur le 02/11/2026 à 17:42"):
            self.assertIn(attendu, m)
        self.assertNotIn("Mobile money", m)  # le paiement annulé n'est pas compté
        self.assertNotIn("Fratrie", m)       # remise d'un autre jour
        self.assertNotIn("Doublon", m)       # remise annulée

    def test_un_comptable_ne_resume_que_ses_encaissements(self):
        self.se_connecter("kossi")
        m = self.service.message(JOUR, JOUR)
        self.assertIn("Caissier : Kossi Mensah", m)
        self.assertIn("*Total encaissé : 40 000 FCFA* (1 paiement)", m)
        self.assertIn("*Paiements annulés : 1*", m)
        self.assertNotIn("Ama Dosseh", m)
        self.assertNotIn("Remises", m)  # réservé à l'administrateur
        self.assertNotIn("Bourse", m)

    def test_le_role_lecture_n_a_pas_de_resume(self):
        self.se_connecter("lecteur")
        with self.assertRaises(ErreurMetier):
            self.service.message(JOUR, JOUR)
        with self.assertRaises(ErreurMetier):
            self.service.lien_whatsapp(JOUR, JOUR)

    def test_jour_sans_paiement_et_periode_de_plusieurs_jours(self):
        m = self.service.message("2026-10-01", "2026-10-01")
        self.assertIn("Aucun paiement enregistré", m)
        self.assertNotIn("Total encaissé", m)
        self.assertIn("du 01/11/2026 au 02/11/2026", self.service.message("2026-11-01", JOUR))
        with self.assertRaises(ErreurMetier):
            self.service.message("pas une date", JOUR)

    # --- Le lien WhatsApp et le numéro de la direction ----------------------------------------
    def test_lien_sans_puis_avec_numero(self):
        lien = self.service.lien_whatsapp(JOUR, JOUR)
        self.assertTrue(lien.startswith("https://wa.me/?text="))
        self.assertEqual(unquote(lien.split("?text=", 1)[1]), self.service.message(JOUR, JOUR))
        self.assertEqual(self.service.numero_affiche(), "")

        self.assertEqual(self.service.definir_numero("90 12 34 56"), "22890123456")
        self.assertEqual(self.service.numero_affiche(), "+228 90 12 34 56")
        self.assertTrue(self.service.lien_whatsapp(JOUR, JOUR).startswith(
            "https://wa.me/22890123456?text="))

        self.assertIsNone(self.service.definir_numero(""))  # retirer le numéro
        self.assertEqual(self.service.numero(), "")

    def test_numero_invalide_et_droits(self):
        for faux in ("12345", "abcdefgh"):
            with self.assertRaises(ErreurMetier):
                self.service.definir_numero(faux)
        self.service.definir_numero("+233 24 123 4567")
        self.assertEqual(self.service.numero_affiche(), "+233241234567")
        for login in ("kossi", "lecteur"):
            self.se_connecter(login)
            with self.assertRaises(ErreurMetier):
                self.service.definir_numero("90 12 34 56")
            self.assertFalse(self.service.peut_definir_numero())
        self.assertEqual(self.service.numero(), "233241234567")  # lecture permise

    def test_un_gros_resume_reste_dans_un_lien_ouvrable(self):
        mode = dict.fromkeys(("especes", "cheque", "virement", "mobile_money"), 0)
        caissiers = [{"nom": f"Caissier numéro {i}", "nb": 1, "total": 1000,
                      "par_mode": mode, "paiements": []} for i in range(30)]
        annules = [{"numero_recu": f"REC-2026-{i:06d}", "montant": 1000,
                    "motif_annulation": "é" * 50} for i in range(60)]
        cloture = {"debut": JOUR, "fin": JOUR, "portee": "Tous les caissiers",
                   "genere_par": "Admin", "caissiers": caissiers,
                   "par_mode": dict(mode, especes=30000), "total": 30000, "nb": 30,
                   "annules": {"nb": 60, "total": 60000, "paiements": annules}}
        remises = [{"nom": "Nom", "prenom": "Prénom", "classe": "6e A", "montant": 1000,
                    "motif": "é" * 50} for _ in range(60)]
        service = ResumeJourService(
            SimpleNamespace(cloture=lambda d, f: cloture),
            SimpleNamespace(remises_periode=lambda d, f: remises, numero=lambda: ""),
            None, ecole=lambda: ECOLE, maintenant=lambda: MAINTENANT)
        lien = service.lien_whatsapp(JOUR, JOUR)
        self.assertLessEqual(len(lien), 1900)
        texte = unquote(lien.split("?text=", 1)[1])
        self.assertIn("*Paiements annulés : 60*", texte)  # les totaux restent toujours
        self.assertIn("*Remises accordées : 60*", texte)
        self.assertIn("Total encaissé : 30 000 FCFA", texte)

    # --- Journal d'audit ---------------------------------------------------------------------
    def test_le_resume_et_le_numero_sont_journalises_sans_le_numero(self):
        journal = JournalService(JournalRepository(self.conn), self.auth)
        service = Audite(self.service, journal, audit_regles.regles_resume())
        service.definir_numero("90 12 34 56")
        service.lien_whatsapp(JOUR, JOUR)
        lignes = journal.repo.lister("2000-01-01", "2100-01-01")
        self.assertEqual([l["action"] for l in lignes], ["caisse.resume", "caisse.numero"])
        self.assertIn("02/11/2026", lignes[0]["detail"])
        for ligne in lignes:
            self.assertNotIn("22890123456", ligne["detail"])
            self.assertNotIn("90 12 34 56", ligne["detail"])
        with self.assertRaises(ErreurMetier):
            service.definir_numero("12345")  # refusé : rien n'est journalisé
        self.assertEqual(len(journal.repo.lister("2000-01-01", "2100-01-01")), 2)


if __name__ == "__main__":
    unittest.main()