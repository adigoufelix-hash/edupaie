import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.classe_repository import ClasseRepository
from edupaie.repositories.contact_repository import ContactRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.classe_service import ClasseService
from edupaie.services.echeancier_service import EcheancierService
from edupaie.services.frais_service import FraisService
from edupaie.services.paiement_service import ErreurMetier

ANNEE = "2026-2027"


class TestClasses(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.eleves = EleveRepository(self.conn)
        self.classes = ClasseService(ClasseRepository(self.conn))
        self.frais = FraisService(FraisRepository(self.conn))
        self.echeancier = EcheancierService(
            EcheanceRepository(self.conn), self.eleves, PaiementRepository(self.conn),
            ContactRepository(self.conn))

    def tearDown(self):
        self.conn.close()

    def eleve(self, classe, nom="A"):
        return self.eleves.ajouter(Eleve(None, nom, "Un", classe, ANNEE, 1000))

    def test_ajout_dans_l_ordre(self):
        for nom in ("6e A", "6e B", "5e A"):
            self.classes.ajouter(nom)
        self.assertEqual(self.classes.noms(), ["6e A", "6e B", "5e A"])

    def test_doublons_et_noms_invalides_refuses(self):
        self.classes.ajouter("6e A")
        for faux in ("6E a", "", "   ", "x" * 31):
            with self.assertRaises(ErreurMetier):
                self.classes.ajouter(faux)

    def test_ajout_en_lot(self):
        self.assertEqual(
            self.classes.ajouter_plusieurs(["6e A", " 6e B ", "", "6e A", "6E b"]), (2, 2))
        with self.assertRaises(ErreurMetier):
            self.classes.ajouter_plusieurs(["5e A", "x" * 31])
        self.assertEqual(self.classes.noms(), ["6e A", "6e B"])  # l'erreur annule tout

    def test_serie(self):
        self.assertEqual(self.classes.serie("6e", "A B, C;D"),
                         ["6e A", "6e B", "6e C", "6e D"])
        self.assertEqual(self.classes.serie("Tle", ""), ["Tle"])
        with self.assertRaises(ErreurMetier):
            self.classes.serie("", "A")

    def test_les_classes_des_donnees_suivent_celles_de_la_liste(self):
        self.classes.ajouter("6e A")
        self.eleve("5e B")
        self.frais.ajouter_ligne("4e C", ANNEE, "Scolarité", 1000)
        self.assertEqual(self.classes.noms(), ["6e A", "4e C", "5e B"])

    def test_les_listes_de_choix_voient_les_nouvelles_classes(self):
        self.classes.ajouter("Nouvelle")
        self.assertIn("Nouvelle", self.frais.classes())
        self.assertIn("Nouvelle", self.echeancier.classes())

    def test_renommer_propage_partout(self):
        self.classes.ajouter("6e A")  # la classe est créée, puis utilisée
        self.eleve("6e A")
        self.frais.ajouter_ligne("6e A", ANNEE, "Scolarité", 100000)
        self.echeancier.ajouter_ligne("6e A", ANNEE, "T1", "2026-10-15", 50)
        self.classes.renommer("6e A", "6e Alpha")
        self.assertEqual(self.conn.execute("SELECT classe FROM eleve").fetchone()[0], "6e Alpha")
        self.assertEqual(self.frais.total("6e Alpha", ANNEE), 100000)
        self.assertEqual(self.frais.total("6e A", ANNEE), 0)
        self.assertEqual(len(self.echeancier.lister("6e Alpha", ANNEE)), 1)
        self.assertEqual(self.classes.noms(), ["6e Alpha"])

    def test_renommer_une_classe_qui_n_existe_que_dans_les_donnees(self):
        self.eleve("5e B")  # jamais ajoutée dans l'écran « Classes »
        self.classes.renommer("5e B", "5e Bleue")
        self.assertEqual(self.conn.execute("SELECT classe FROM eleve").fetchone()[0], "5e Bleue")
        self.assertEqual(self.classes.noms(), ["5e Bleue"])

    def test_renommer_refuse_un_nom_existant_mais_accepte_un_changement_de_casse(self):
        self.classes.ajouter("6e A")
        self.classes.ajouter("6e B")
        with self.assertRaises(ErreurMetier):
            self.classes.renommer("6e A", "6E b")
        self.classes.renommer("6e A", "6e a")
        self.assertEqual(self.classes.noms(), ["6e a", "6e B"])

    def test_supprimer(self):
        self.classes.ajouter("6e A")
        self.classes.ajouter("6e B")
        self.eleve("6e B")
        self.classes.supprimer("6e A")
        self.assertEqual(self.classes.noms(), ["6e B"])
        with self.assertRaises(ErreurMetier) as contexte:
            self.classes.supprimer("6e B")
        self.assertIn("élève", str(contexte.exception))
        with self.assertRaises(ErreurMetier):
            self.classes.supprimer("inconnue")

    def test_deplacer(self):
        for nom in ("6e A", "6e B", "6e C"):
            self.classes.ajouter(nom)
        self.assertTrue(self.classes.deplacer("6e C", -1))
        self.assertEqual(self.classes.noms(), ["6e A", "6e C", "6e B"])
        self.assertFalse(self.classes.deplacer("6e A", -1))  # déjà en tête
        self.eleve("5e Z")  # classe présente seulement dans les données
        self.assertEqual(self.classes.noms()[-1], "5e Z")
        self.classes.deplacer("5e Z", -1)
        self.assertEqual(self.classes.noms(), ["6e A", "6e C", "5e Z", "6e B"])

    def test_comptages(self):
        self.classes.ajouter("6e A")
        self.classes.ajouter("6e B")
        self.eleve("6e A")
        self.eleve("6e a", nom="B")  # même classe, casse différente
        self.frais.ajouter_ligne("6e A", ANNEE, "Scolarité", 1000)
        lignes = {l["nom"]: l for l in self.classes.lister()}
        self.assertEqual((lignes["6e A"]["eleves"], lignes["6e A"]["frais"],
                          lignes["6e A"]["supprimable"]), (2, 1, False))
        self.assertTrue(lignes["6e B"]["supprimable"])
        self.assertEqual(len(lignes), 2)

    def test_seul_un_admin_gere_les_classes(self):
        utilisateurs = UtilisateurRepository(self.conn)
        auth = AuthService(utilisateurs)
        service = ClasseService(ClasseRepository(self.conn), auth)
        for nom, role in (("caisse", "comptable"), ("admin", "admin")):
            identifiant = utilisateurs.creer(nom, nom, "x", role)
            auth.utilisateur = {"id": identifiant, "login": nom,
                                "nom_complet": nom, "role": role}
            if role == "comptable":
                with self.assertRaises(ErreurMetier):
                    service.ajouter("6e A")
                self.assertEqual(service.noms(), [])  # la lecture reste permise
            else:
                service.ajouter("6e A")
                self.assertEqual(service.noms(), ["6e A"])


if __name__ == "__main__":
    unittest.main()