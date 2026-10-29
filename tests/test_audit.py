import contextlib
import io
import sqlite3
import unittest
from datetime import datetime

from edupaie.models.entities import Eleve
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.classe_repository import ClasseRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.repositories.verification_repository import VerificationRepository
from edupaie.services import audit_regles
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.classe_service import ClasseService
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.verification_service import VerificationService

DEBUT, FIN = "2000-01-01", "2100-01-01"


class FauxEleveService:
    """Même interface que EleveService, pour tester les règles du journal."""

    def __init__(self):
        self.liste = [Eleve(1, "Kouassi", "Kofi", "6e A", "2026-2027", 100000)]

    def lister(self):
        return list(self.liste)

    def enregistrer(self, eleve_id, nom, prenom, classe, annee, total):
        return 2 if eleve_id is None else None

    def supprimer(self, eleve_id):
        return None


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.utilisateurs = UtilisateurRepository(self.conn)
        self.auth = AuthService(self.utilisateurs)
        self.comptes = {
            "admin": (self.utilisateurs.creer("admin", "Administrateur", "x", "admin"),
                      "Administrateur", "admin"),
            "caisse": (self.utilisateurs.creer("caisse", "Caissier", "x", "comptable"),
                       "Caissier", "comptable"),
        }
        self.journal = JournalService(JournalRepository(self.conn), self.auth)
        self.se_connecter("admin")

    def tearDown(self):
        self.conn.close()

    def se_connecter(self, nom):
        identifiant, nom_complet, role = self.comptes[nom]
        self.auth.utilisateur = {"id": identifiant, "login": nom,
                                 "nom_complet": nom_complet, "role": role}

    def lignes(self):  # lecture directe : indépendante des droits de l'utilisateur
        return self.journal.repo.lister(DEBUT, FIN)

    def remplir(self, n=3):
        for i in range(n):
            self.journal.journaliser("eleve.creation", f"Élève {i}", "eleve", i)

    def sans_protection(self):
        self.conn.execute("DROP TRIGGER audit_pas_de_modification")
        self.conn.execute("DROP TRIGGER audit_pas_de_suppression")

    # --- Journal et chaîne ---------------------------------------------------------
    def test_un_evenement_est_enregistre_avec_son_auteur(self):
        self.journal.journaliser("eleve.creation", "Kouassi Kofi", "eleve", 1)
        ligne = self.journal.consulter(DEBUT, FIN)[0]
        self.assertEqual((ligne["utilisateur"], ligne["action"], ligne["objet_id"]),
                         ("Administrateur", "eleve.creation", 1))

    def test_le_journal_est_verifiable_et_protege(self):
        self.assertTrue(self.journal.verifier()["ok"])
        self.remplir()
        resultat = self.journal.verifier()
        self.assertTrue(resultat["ok"])
        self.assertEqual(resultat["nb"], 3)
        with self.assertRaises(sqlite3.Error):
            self.conn.execute("UPDATE audit SET detail = 'x'")
        with self.assertRaises(sqlite3.Error):
            self.conn.execute("DELETE FROM audit")
        self.assertEqual(self.journal.verifier()["nb"], 3)

    def test_une_modification_directe_est_detectee(self):
        self.remplir()
        self.sans_protection()
        self.conn.execute("UPDATE audit SET detail = 'Élève trafiqué' WHERE id = 2")
        self.conn.commit()
        resultat = self.journal.verifier()
        self.assertFalse(resultat["ok"])
        self.assertIn("n°2", resultat["message"])

    def test_des_evenements_supprimes_sont_detectes(self):
        for condition in ("id = 2", "id = 1", "id = 3"):  # milieu, début, fin
            with self.subTest(condition=condition):
                self.tearDown()
                self.setUp()
                self.remplir()
                self.sans_protection()
                self.conn.execute(f"DELETE FROM audit WHERE {condition}")
                self.conn.commit()
                self.assertFalse(self.journal.verifier()["ok"])

    def test_filtres_de_consultation(self):
        horloge = iter([datetime(2026, 10, 1, 9, 0), datetime(2026, 10, 15, 10, 0),
                        datetime(2026, 10, 20, 11, 30)])
        self.journal.maintenant = lambda: next(horloge)
        self.journal.journaliser("paiement.enregistrement", "Reçu 1", "paiement", 1)
        self.se_connecter("caisse")
        self.journal.journaliser("eleve.creation", "100% remise", "eleve", 2)
        self.se_connecter("admin")
        self.journal.journaliser("remise.accordee", "Autre", "remise", 3)
        consulter = self.journal.consulter
        self.assertEqual(len(consulter("2026-10-01", "2026-10-31")), 3)
        self.assertEqual(len(consulter("2026-10-10", "2026-10-20")), 2)
        self.assertEqual([l["action"] for l in consulter(DEBUT, FIN, categorie="Paiements")],
                         ["paiement.enregistrement"])
        self.assertEqual(len(consulter(DEBUT, FIN, utilisateur="Caissier")), 1)
        self.assertEqual(len(consulter(DEBUT, FIN, recherche="%")), 1)  # pas un joker
        self.assertEqual(len(consulter(DEBUT, FIN, recherche="reçu 1")), 1)
        with self.assertRaises(ErreurMetier):
            consulter("pas une date", FIN)
        with self.assertRaises(ErreurMetier):
            consulter(FIN, DEBUT)

    def test_le_journal_est_reserve_a_l_admin(self):
        self.se_connecter("caisse")
        with self.assertRaises(ErreurMetier):
            self.journal.consulter(DEBUT, FIN)
        with self.assertRaises(ErreurMetier):
            self.journal.verifier()

    # --- Règles par service ------------------------------------------------------------
    def test_paiement_et_annulation_sont_journalises(self):
        eleves, paiements = EleveRepository(self.conn), PaiementRepository(self.conn)
        eleve = eleves.ajouter(Eleve(None, "Kouassi", "Kofi", "6e A", "2026-2027", 100000))
        service = Audite(PaiementService(eleves, paiements, self.auth), self.journal,
                         audit_regles.regles_paiement())
        paiement = service.enregistrer_paiement(eleve, 40000, "2026-09-01", "especes")
        service.annuler_paiement(paiement.id, "Montant saisi par erreur")
        lignes = self.journal.consulter(DEBUT, FIN)
        self.assertEqual([l["action"] for l in lignes],
                         ["paiement.annulation", "paiement.enregistrement"])
        self.assertIn("40 000 FCFA", lignes[1]["detail"])
        self.assertIn("Kouassi Kofi", lignes[1]["detail"])
        self.assertIn("Montant saisi par erreur", lignes[0]["detail"])
        self.assertEqual(lignes[1]["utilisateur"], "Administrateur")

    def test_une_operation_refusee_n_est_pas_journalisee(self):
        eleves, paiements = EleveRepository(self.conn), PaiementRepository(self.conn)
        eleve = eleves.ajouter(Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        service = Audite(PaiementService(eleves, paiements, self.auth), self.journal,
                         audit_regles.regles_paiement())
        with self.assertRaises(ErreurMetier):
            service.enregistrer_paiement(eleve, 999999, "2026-09-01", "especes")
        self.assertEqual(self.lignes(), [])

    def test_le_mot_de_passe_n_est_jamais_journalise(self):
        auth_ui = Audite(self.auth, self.journal, audit_regles.regles_auth())
        auth_ui.creer_utilisateur("jean", "Jean", "Secret2026", "comptable")
        auth_ui.deconnecter()
        auth_ui.authentifier("jean", "Secret2026")
        auth_ui.changer_mon_mot_de_passe("Secret2026", "Nouveau2026")
        lignes = self.lignes()
        texte = " ".join(l["detail"] for l in lignes)
        self.assertNotIn("Secret2026", texte)
        self.assertNotIn("Nouveau2026", texte)
        self.assertEqual([l["action"] for l in lignes],
                         ["utilisateur.mdp_change", "connexion", "utilisateur.creation"])

    def test_echecs_et_blocage_de_connexion(self):
        auth_ui = Audite(self.auth, self.journal, audit_regles.regles_auth())
        auth_ui.creer_utilisateur("jean", "Jean", "Secret2026", "comptable")
        auth_ui.deconnecter()
        for _ in range(5):
            self.assertIsNone(auth_ui.authentifier("jean", "Mauvais123"))
        with self.assertRaises(ErreurMetier):
            auth_ui.authentifier("jean", "Secret2026")
        actions = [l["action"] for l in self.lignes()]
        self.assertEqual(actions.count("echec_connexion"), 5)
        self.assertEqual(actions.count("blocage_connexion"), 1)
        self.assertNotIn("connexion", actions)

    def test_eleve_creation_modification_suppression(self):
        service = Audite(FauxEleveService(), self.journal, audit_regles.regles_eleve())
        service.enregistrer(None, "Mensah", "Ama", "6e B", "2026-2027", "80000")
        service.enregistrer(1, "Kouassi-Mensah", "Kofi", "6e A", "2026-2027", "120000")
        service.supprimer(1)
        par_action = {l["action"]: l for l in self.lignes()}
        self.assertEqual(par_action["eleve.creation"]["objet_id"], 2)
        self.assertIn("Mensah Ama (6e B, 2026-2027) - total 80 000 FCFA",
                      par_action["eleve.creation"]["detail"])
        modification = par_action["eleve.modification"]["detail"]
        self.assertIn("nom : Kouassi → Kouassi-Mensah", modification)
        self.assertIn("total : 100 000 FCFA → 120 000 FCFA", modification)
        self.assertNotIn("classe :", modification)  # inchangée : pas mentionnée
        self.assertEqual(par_action["eleve.suppression"]["detail"],
                         "Kouassi Kofi (6e A, 2026-2027)")

    def test_classes_et_recus_douteux(self):
        classes = Audite(ClasseService(ClasseRepository(self.conn)), self.journal,
                         audit_regles.regles_classe())
        classes.ajouter("6e A")
        classes.renommer("6e A", "6e Alpha")
        verif = Audite(VerificationService(VerificationRepository(self.conn)), self.journal,
                       audit_regles.regles_verification())
        verif.verifier("REC-2030-999999")   # introuvable : signalé
        verif.verifier("n'importe quoi")    # illisible : pas signalé
        self.assertEqual([l["action"] for l in self.lignes()],
                         ["recu.alerte", "classe.renommage", "classe.ajout"])

    def test_une_panne_du_journal_ne_bloque_pas_le_travail(self):
        class JournalCasse:
            def journaliser(self, **entree):
                raise sqlite3.OperationalError("disque plein")

        eleves, paiements = EleveRepository(self.conn), PaiementRepository(self.conn)
        eleve = eleves.ajouter(Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        service = Audite(PaiementService(eleves, paiements, self.auth), JournalCasse(),
                         audit_regles.regles_paiement())
        with contextlib.redirect_stderr(io.StringIO()):
            paiement = service.enregistrer_paiement(eleve, 40000, "2026-09-01", "especes")
        self.assertEqual(paiement.montant, 40000)


if __name__ == "__main__":
    unittest.main()