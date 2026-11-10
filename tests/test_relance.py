import sqlite3
import unittest
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import unquote

from edupaie.models.entities import Eleve
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.contact_repository import ContactRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.relance_repository import RelanceRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services import audit_regles
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.echeancier_service import EcheancierService
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.relance_service import RelanceService

REF = "2026-11-05"
AYIVI, DOSSEH = "22890123456", "22891000000"


class Horloge:
    def __init__(self, quand):
        self.quand = quand

    def __call__(self):
        return self.quand


class TestRelance(unittest.TestCase):
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
                                 ("lecteur", "Lecteur", "lecture")):
            self.comptes[login] = {"id": utilisateurs.creer(login, nom, "x", role),
                                   "login": login, "nom_complet": nom, "role": role}
        eleves = EleveRepository(self.conn)
        paiements = PaiementRepository(self.conn)
        self.echeancier = EcheancierService(EcheanceRepository(self.conn), eleves, paiements,
                                            ContactRepository(self.conn))
        echeances = EcheanceRepository(self.conn)
        echeances.ajouter("6e A", "2026-2027", "T1", "2026-10-15", 50)
        echeances.ajouter("6e A", "2026-2027", "T2", "2026-12-15", 50)
        self.ids = {}
        for cle, nom, prenom in (("ama", "Ayivi", "Ama"), ("bob", "Ayivi", "Bob"),
                                 ("cleo", "Dosseh", "Cléo"), ("dan", "Kodjo", "Dan"),
                                 ("eve", "Mensah", "Eve")):
            self.ids[cle] = eleves.ajouter(Eleve(None, nom, prenom, "6e A", "2026-2027", 100000))
        # Ama et Bob sont frères et sœurs ; Dan n'a pas de contact
        self.echeancier.enregistrer_contact(self.ids["ama"], "Mme Ayivi", "90 12 34 56")
        self.echeancier.enregistrer_contact(self.ids["bob"], "Mme Ayivi", "+228 90 12 34 56")
        self.echeancier.enregistrer_contact(self.ids["cleo"], "M. Dosseh", "91 00 00 00")
        paie = PaiementService(eleves, paiements, self.auth)
        self.auth.utilisateur = self.comptes["kossi"]
        paie.enregistrer_paiement(self.ids["bob"], 20000, "2026-10-01", "especes")
        paie.enregistrer_paiement(self.ids["eve"], 100000, "2026-10-01", "especes")

        self.horloge = Horloge(datetime(2026, 11, 5, 10, 0))
        self.repo = RelanceRepository(self.conn)
        self.service = RelanceService(self.echeancier, self.repo, self.auth,
                                      maintenant=self.horloge)

    def tearDown(self):
        self.conn.close()

    def test_un_parent_un_message(self):
        p = self.service.preparer(REF)
        # Ama 50 000 + Bob 30 000 + Cléo 50 000 + Dan 50 000 ; Eve a tout payé
        self.assertEqual((p["nb_eleves"], p["total_retard"]), (4, 180000))
        self.assertEqual([d["cle"] for d in p["destinataires"]], [AYIVI, DOSSEH])
        ayivi, dosseh = p["destinataires"]
        self.assertEqual((ayivi["nb_eleves"], ayivi["retard"], ayivi["tuteur"]),
                         (2, 80000, "Mme Ayivi"))
        for attendu in ("2 de vos enfants", "Ayivi Ama", "Ayivi Bob", "50 000 FCFA",
                        "30 000 FCFA", "Total en retard : 80 000 FCFA"):
            self.assertIn(attendu, ayivi["message"])
        # un seul enfant : le message habituel de l'écran Impayés
        self.assertEqual(dosseh["message"], self.echeancier.message_relance(dosseh["enfants"][0]))
        self.assertEqual([e["nom"] for e in p["sans_numero"]], ["Kodjo Dan"])
        self.assertEqual((ayivi["derniere"], ayivi["jours_depuis"], ayivi["recente"]),
                         (None, None, False))

    def test_filtre_par_classe(self):
        self.assertEqual(self.service.preparer(REF, "6e A")["nb_eleves"], 4)
        self.assertEqual(self.service.preparer(REF, "5e B")["destinataires"], [])
        self.assertEqual(self.service.preparer("2026-10-01")["destinataires"], [])  # rien d'échu

    def test_la_relance_est_notee_et_le_delai_respecte(self):
        r = self.service.lien_et_noter(REF, None, AYIVI)
        self.assertEqual((r["nb_eleves"], r["retard"]), (2, 80000))
        self.assertTrue(r["lien"].startswith(f"https://wa.me/{AYIVI}?text="))
        self.assertIn("Total en retard : 80 000 FCFA", unquote(r["lien"]))
        notees = self.repo.dernieres(self.ids.values())
        self.assertEqual(set(notees), {self.ids["ama"], self.ids["bob"]})  # les deux enfants

        d = {x["cle"]: x for x in self.service.preparer(REF)["destinataires"]}
        self.assertEqual((d[AYIVI]["jours_depuis"], d[AYIVI]["recente"]), (0, True))
        self.assertFalse(d[DOSSEH]["recente"])
        self.horloge.quand = datetime(2026, 11, 10, 9, 0)  # 5 jours plus tard
        d = {x["cle"]: x for x in self.service.preparer(REF)["destinataires"]}
        self.assertEqual((d[AYIVI]["jours_depuis"], d[AYIVI]["recente"]), (5, True))
        self.horloge.quand = datetime(2026, 11, 14, 9, 0)  # 9 jours plus tard
        d = {x["cle"]: x for x in self.service.preparer(REF)["destinataires"]}
        self.assertEqual((d[AYIVI]["jours_depuis"], d[AYIVI]["recente"]), (9, False))
        self.assertEqual(len(self.repo.historique(self.ids["ama"])), 1)

    def test_parents_introuvables(self):
        for cle in ("22899999999", "sans-numero", ""):
            with self.assertRaises(ErreurMetier):
                self.service.lien_et_noter(REF, None, cle)
        # un parent qui a payé entre-temps n'est plus à relancer
        self.auth.utilisateur = self.comptes["kossi"]
        paie = PaiementService(EleveRepository(self.conn), PaiementRepository(self.conn), self.auth)
        paie.enregistrer_paiement(self.ids["cleo"], 50000, "2026-11-04", "especes")
        with self.assertRaises(ErreurMetier):
            self.service.lien_et_noter(REF, None, DOSSEH)
        self.assertEqual(self.repo.dernieres(self.ids.values()), {})  # rien n'a été noté

    def test_droits(self):
        self.auth.utilisateur = self.comptes["admin"]
        self.assertEqual(self.service.preparer(REF)["nb_eleves"], 4)
        self.auth.utilisateur = self.comptes["lecteur"]
        with self.assertRaises(ErreurMetier):
            self.service.preparer(REF)
        with self.assertRaises(ErreurMetier):
            self.service.lien_et_noter(REF, None, AYIVI)

    def test_un_gros_foyer_reste_dans_un_lien_ouvrable(self):
        enfants = [{"eleve_id": i, "nom": f"Nom très long numéro {i} Prénom assez long",
                    "classe": "6e A", "tranche": "Première tranche", "date_limite": "2026-10-15",
                    "jours": 21, "exigible": 50000, "paye": 0, "retard": 50000,
                    "tuteur": "Mme Foyer", "telephone": "90 12 34 56"} for i in range(1, 13)]
        faux = SimpleNamespace(
            impayes=lambda d, c: {"date_ref": REF, "lignes": enfants, "total_retard": 600000,
                                  "sans_echeancier": 0},
            classes=lambda: [], message_relance=lambda ligne: "x")
        service = RelanceService(faux, SimpleNamespace(dernieres=lambda ids: {},
                                                       ajouter=lambda *a: None),
                                 None, maintenant=self.horloge)
        r = service.lien_et_noter(REF, None, AYIVI)
        self.assertEqual((r["nb_eleves"], r["retard"]), (12, 600000))
        self.assertLessEqual(len(r["lien"]), 1900)
        texte = unquote(r["lien"].split("?text=", 1)[1])
        self.assertIn("12 de vos enfants", texte)
        self.assertIn("Total en retard : 600 000 FCFA", texte)

    def test_le_journal_ne_garde_que_des_totaux(self):
        self.auth.utilisateur = self.comptes["kossi"]
        journal = JournalService(JournalRepository(self.conn), self.auth)
        service = Audite(self.service, journal, audit_regles.regles_relance())
        service.lien_et_noter(REF, None, AYIVI)
        with self.assertRaises(ErreurMetier):
            service.lien_et_noter(REF, None, "22899999999")  # refusé : rien n'est journalisé
        lignes = journal.repo.lister("2000-01-01", "2100-01-01")
        self.assertEqual([x["action"] for x in lignes], ["impayes.relance"])
        self.assertIn("2 élève(s), 80 000 FCFA en retard", lignes[0]["detail"])
        for secret in ("Ayivi", "Ama", "22890", "90 12"):
            self.assertNotIn(secret, lignes[0]["detail"])


if __name__ == "__main__":
    unittest.main()