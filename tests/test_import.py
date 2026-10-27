import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.import_repository import ImportRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.frais_service import FraisService
from edupaie.services.import_service import ImportEleveService, _annee_courante
from edupaie.services.paiement_service import ErreurMetier

ENTETES = ["Nom", "Prénom", "Classe", "Année scolaire", "Total dû (FCFA)",
           "Parent / tuteur", "Téléphone"]


def ligne_ok(**modifications):
    ligne = {"ligne": 2, "nom": "A", "prenom": "Un", "classe": "6e A",
             "annee": "2026-2027", "total": 1000, "tuteur": "", "telephone": "",
             "statut": "ok", "message": ""}
    ligne.update(modifications)
    return ligne


class TestImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.eleves = EleveRepository(self.conn)
        self.frais = FraisService(FraisRepository(self.conn))
        self.service = ImportEleveService(
            ImportRepository(self.conn), self.eleves, self.frais)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def classeur(self, lignes, nom="eleves.xlsx"):
        classeur = Workbook()
        feuille = classeur.active
        for ligne in lignes:
            feuille.append(ligne)
        chemin = Path(self.tmp.name) / nom
        classeur.save(chemin)
        return chemin

    def nb_eleves(self):
        return self.conn.execute("SELECT COUNT(*) FROM eleve").fetchone()[0]

    def test_import_complet_avec_contacts(self):
        chemin = self.classeur([
            ENTETES,
            ["Kouassi", "Kofi", "6e A", "2026-2027", 100000, "M. Kouassi", "90 12 34 56"],
            ["Mensah", "Ama", "6e A", "2026-2027", "120 000 FCFA", None, None],
            ["Diallo", "Fatou", "5e B", "2026-2027", 150000.0, None, "+233 24 123 4567"]])
        analyse = self.service.analyser(chemin)
        self.assertEqual((analyse["nb_ok"], analyse["nb_ignores"], analyse["nb_erreurs"]),
                         (3, 0, 0))
        self.assertEqual([l["total"] for l in analyse["lignes"]], [100000, 120000, 150000])
        self.assertEqual(self.nb_eleves(), 0)  # l'aperçu n'enregistre rien
        self.assertEqual(self.service.importer(analyse), 3)
        self.assertEqual(self.nb_eleves(), 3)
        contacts = self.conn.execute(
            "SELECT tuteur, telephone FROM contact_eleve ORDER BY eleve_id").fetchall()
        self.assertEqual(len(contacts), 2)
        self.assertEqual(contacts[0]["tuteur"], "M. Kouassi")

    def test_en_tetes_sans_accents_ni_casse_et_en_desordre(self):
        chemin = self.classeur([["CLASSE", "prenom", "NOM", "Annee", "Frais"],
                                ["6e A", "Kofi", "Kouassi", 2026, 100000]])
        l = self.service.analyser(chemin)["lignes"][0]
        self.assertEqual((l["nom"], l["prenom"], l["classe"], l["annee"], l["total"]),
                         ("Kouassi", "Kofi", "6e A", "2026-2027", 100000))

    def test_titre_avant_l_en_tete_et_numeros_de_ligne_excel(self):
        chemin = self.classeur([
            ["Liste des élèves"], [None], ENTETES,
            ["Kouassi", "Kofi", "6e A", "2026-2027", 100000, None, None],
            ["", "Ama", "6e A", "2026-2027", 100000, None, None]])
        analyse = self.service.analyser(chemin)
        self.assertEqual([l["ligne"] for l in analyse["lignes"]], [4, 5])
        self.assertEqual([l["statut"] for l in analyse["lignes"]], ["ok", "erreur"])
        self.assertIn("Nom manquant", analyse["lignes"][1]["message"])

    def test_total_vide_utilise_les_frais_de_la_classe(self):
        self.frais.ajouter_ligne("6e A", "2026-2027", "Scolarité", 150000)
        chemin = self.classeur([
            ENTETES, ["A", "Un", "6e A", "2026-2027", None, None, None],
            ["B", "Deux", "6e B", "2026-2027", None, None, None]])
        lignes = self.service.analyser(chemin)["lignes"]
        self.assertEqual((lignes[0]["statut"], lignes[0]["total"]), ("ok", 150000))
        self.assertEqual(lignes[1]["statut"], "erreur")

    def test_annees(self):
        annees = ["2026/2027", "2026 - 2027", 2026, "2026-2028", "abc", None]
        lignes = [ENTETES] + [[f"N{i}", "P", "6e A", a, 1000, None, None]
                              for i, a in enumerate(annees)]
        resultat = self.service.analyser(self.classeur(lignes))["lignes"]
        self.assertEqual([l["statut"] for l in resultat],
                         ["ok", "ok", "ok", "erreur", "erreur", "ok"])
        self.assertEqual([l["annee"] for l in resultat[:3]], ["2026-2027"] * 3)
        self.assertEqual(resultat[5]["annee"], _annee_courante())

    def test_totaux(self):
        valeurs = ["150 000 FCFA", 150000.0, "abc", 0, -5, 1500.5, "1,5"]
        lignes = [ENTETES] + [[f"N{i}", "P", "6e A", "2026-2027", v, None, None]
                              for i, v in enumerate(valeurs)]
        resultat = self.service.analyser(self.classeur(lignes))["lignes"]
        self.assertEqual([l["statut"] for l in resultat],
                         ["ok", "ok", "erreur", "erreur", "erreur", "erreur", "erreur"])

    def test_telephone(self):
        chemin = self.classeur([
            ENTETES, ["A", "Un", "6e A", "2026-2027", 1000, None, "12345"],
            ["B", "Deux", "6e A", "2026-2027", 1000, None, "90 12 34 56"]])
        lignes = self.service.analyser(chemin)["lignes"]
        self.assertEqual([l["statut"] for l in lignes], ["erreur", "ok"])

    def test_doublons_ignores_puis_reimport_sans_effet(self):
        self.eleves.ajouter(Eleve(None, "Kouassi", "Kofi", "6e A", "2026-2027", 100000))
        chemin = self.classeur([
            ENTETES,
            ["KOUASSI", "kofi", "6e A", "2026-2027", 100000, None, None],
            ["Zoé", "Ama", "6e A", "2026-2027", 100000, None, None],
            ["ZOE", "AMA", "6e A", "2026-2027", 100000, None, None],
            ["Autre", "Élève", "6e A", "2026-2027", 100000, None, None]])
        analyse = self.service.analyser(chemin)
        self.assertEqual([l["statut"] for l in analyse["lignes"]],
                         ["ignore", "ok", "ignore", "ok"])
        self.assertEqual(self.service.importer(analyse), 2)
        self.assertEqual(self.nb_eleves(), 3)
        analyse = self.service.analyser(chemin)
        self.assertEqual(analyse["nb_ok"], 0)
        with self.assertRaises(ErreurMetier):
            self.service.importer(analyse)

    def test_fichiers_invalides(self):
        with self.assertRaises(ErreurMetier):  # colonne Classe absente
            self.service.analyser(self.classeur([["Nom", "Prénom"], ["A", "B"]]))
        with self.assertRaises(ErreurMetier):  # classeur vide
            self.service.analyser(self.classeur([], "vide.xlsx"))
        faux = Path(self.tmp.name) / "faux.xlsx"
        faux.write_text("pas un classeur", encoding="utf-8")
        with self.assertRaises(ErreurMetier):
            self.service.analyser(faux)
        csv = Path(self.tmp.name) / "eleves.csv"
        csv.write_text("Nom;Prénom;Classe", encoding="utf-8")
        with self.assertRaises(ErreurMetier):
            self.service.analyser(csv)
        with self.assertRaises(ErreurMetier):
            self.service.analyser(Path(self.tmp.name) / "inexistant.xlsx")

    def test_limite_de_lignes(self):
        self.service.max_lignes = 3
        lignes = [ENTETES] + [[f"N{i}", "P", "6e A", "2026-2027", 1000, None, None]
                              for i in range(5)]
        with self.assertRaises(ErreurMetier):
            self.service.analyser(self.classeur(lignes))
        self.assertEqual(self.service.analyser(self.classeur(lignes[:4], "ok.xlsx"))["nb_ok"], 3)

    def test_import_tout_ou_rien(self):
        with self.assertRaises(ErreurMetier):
            self.service.importer({"lignes": [ligne_ok(), ligne_ok(nom="B", total=None)]})
        self.assertEqual(self.nb_eleves(), 0)

    def test_sauvegarde_avant_import(self):
        class Fausse:
            def __init__(self, echec=False):
                self.appels, self.echec = [], echec

            def sauvegarder(self, motif="manuelle", dossier=None):
                self.appels.append(motif)
                if self.echec:
                    raise ErreurMetier("disque plein")

        fausse = Fausse()
        service = ImportEleveService(ImportRepository(self.conn), self.eleves,
                                     self.frais, sauvegarde=fausse)
        service.importer({"lignes": [ligne_ok()]})
        self.assertEqual(fausse.appels, ["avant-import"])
        service = ImportEleveService(ImportRepository(self.conn), self.eleves,
                                     self.frais, sauvegarde=Fausse(echec=True))
        with self.assertRaises(ErreurMetier):
            service.importer({"lignes": [ligne_ok(nom="Z")]})
        self.assertEqual(self.nb_eleves(), 1)  # rien n'a été ajouté après l'échec

    def test_seul_un_admin_importe(self):
        utilisateurs = UtilisateurRepository(self.conn)
        auth = AuthService(utilisateurs)
        service = ImportEleveService(ImportRepository(self.conn), self.eleves,
                                     self.frais, auth)
        chemin = self.classeur([ENTETES, ["A", "Un", "6e A", "2026-2027", 1000, None, None]])
        for nom, role in (("caisse", "comptable"), ("admin", "admin")):
            identifiant = utilisateurs.creer(nom, nom, "x", role)
            auth.utilisateur = {"id": identifiant, "login": nom,
                                "nom_complet": nom, "role": role}
            if role == "comptable":
                with self.assertRaises(ErreurMetier):
                    service.analyser(chemin)
                with self.assertRaises(ErreurMetier):
                    service.importer({"lignes": [ligne_ok()]})
                with self.assertRaises(ErreurMetier):
                    service.creer_modele(self.tmp.name)
            else:
                self.assertEqual(service.analyser(chemin)["nb_ok"], 1)

    def test_le_modele_se_relit_sans_erreur(self):
        modele = self.service.creer_modele(self.tmp.name)
        self.assertTrue(modele.exists())
        analyse = self.service.analyser(modele)
        self.assertEqual((analyse["lignes"], analyse["nb_ok"], analyse["nb_erreurs"]),
                         ([], 0, 0))


if __name__ == "__main__":
    unittest.main()