import html
import re
import sqlite3
import unittest
from types import SimpleNamespace

from edupaie.models.entities import Eleve
from edupaie.permissions import PERMISSIONS, a_permission
from edupaie.repositories.classe_repository import ClasseRepository
from edupaie.repositories.demarrage_repository import DemarrageRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.demarrage_service import DemarrageService
from edupaie.services.ecole import ParametresEcole
from edupaie.services.guide import ARTICLES, ECRANS, ORDRE_CATEGORIES, GuideService


class FauxAuth:
    def __init__(self, role, admins=1, codes=0):
        self.role, self.admins, self.codes = role, admins, codes

    def peut(self, permission):
        return a_permission(self.role, permission)

    def nombre_admins(self):
        return self.admins

    def codes_secours_restants(self):
        return self.codes


class TestGuide(unittest.TestCase):
    def ids(self, role):
        return {a.id for a in GuideService(FauxAuth(role)).articles()}

    def test_les_articles_sont_coherents(self):
        ids = [a.id for a in ARTICLES]
        self.assertEqual(len(ids), len(set(ids)))
        permissions = set().union(*PERMISSIONS.values())
        for a in ARTICLES:
            self.assertTrue(a.titre.strip() and len(a.corps) > 80, a.id)
            self.assertIn(a.categorie, ORDRE_CATEGORIES, a.id)
            self.assertTrue(a.permission is None or a.permission in permissions, a.id)
            self.assertTrue(a.ecran is None or a.ecran in ECRANS, a.id)
            for cible in re.findall(r'href="guide:([a-z_]+)"', a.corps):
                self.assertIn(cible, ids, f"{a.id} -> {cible}")
            for cible in re.findall(r'href="ecran:([a-z_]+)"', a.corps):
                self.assertIn(cible, ECRANS, f"{a.id} -> {cible}")

    def test_le_guide_s_adapte_au_role(self):
        self.assertEqual(len(self.ids("admin")), len(ARTICLES))
        self.assertEqual(len(GuideService(None).articles()), len(ARTICLES))
        comptable = self.ids("comptable")
        self.assertTrue({"paiement", "recu", "verifier", "cloture", "impayes", "eleves",
                         "eleve_ajouter", "fiche", "export", "connexion", "faq"} <= comptable)
        self.assertFalse(comptable & {
            "annuler_paiement", "remises", "import", "parametres", "classes", "frais",
            "annees", "utilisateurs", "sauvegardes", "journal", "licence",
            "premier_lancement"})
        lecture = self.ids("lecture")
        self.assertTrue({"eleves", "fiche", "recu", "verifier", "tableau_de_bord"} <= lecture)
        self.assertFalse(lecture & {"paiement", "eleve_ajouter", "cloture", "impayes"})

    def test_categories_dans_l_ordre(self):
        noms = [c for c, _ in GuideService(FauxAuth("admin")).par_categorie()]
        self.assertEqual(noms, ORDRE_CATEGORIES)
        noms = [c for c, _ in GuideService(FauxAuth("lecture")).par_categorie()]
        self.assertEqual(noms, [c for c in ORDRE_CATEGORIES if c in noms])

    # --- Recherche ----------------------------------------------------------------------
    def test_recherche(self):
        service = GuideService(FauxAuth("admin"))
        self.assertEqual(service.rechercher("annuler un paiement")[0].id, "annuler_paiement")
        self.assertEqual(service.rechercher("cloture")[0].id, "cloture")  # sans accent
        self.assertEqual(service.rechercher("CLÔTURE")[0].id, "cloture")
        self.assertEqual(service.rechercher("licence")[0].id, "licence")
        self.assertEqual([a.id for a in service.rechercher("Élève")],
                         [a.id for a in service.rechercher("eleve")])
        self.assertTrue(service.rechercher("annul"))  # début de mot
        for rien in ("zzzzzz", "", "   ", "le la un", "href"):
            self.assertEqual(service.rechercher(rien), [], repr(rien))

    def test_la_recherche_respecte_le_role(self):
        comptable = GuideService(FauxAuth("comptable"))
        self.assertNotIn("licence", {a.id for a in comptable.rechercher("licence")})
        self.assertIsNone(comptable.article("licence"))
        self.assertIsNotNone(comptable.article("paiement"))

    # --- Rendu ---------------------------------------------------------------------------
    def test_rendu_des_articles(self):
        service = GuideService(FauxAuth("admin"), support_whatsapp="22890123456",
                               support_email="contact@exemple.tg")
        for a in service.articles():
            rendu = service.html(a, "#0F766E")
            self.assertNotIn("{support}", rendu, a.id)
            self.assertIn("#0F766E", rendu)
            self.assertIn(html.escape(a.titre), rendu)
        self.assertIn('href="ecran:caisse"', service.html(service.article("cloture"), "#000000"))
        probleme = service.html(service.article("probleme"), "#000000")
        self.assertIn("22890123456", probleme)
        self.assertIn("contact@exemple.tg", probleme)
        sans = GuideService(FauxAuth("admin"), support_whatsapp="", support_email="")
        self.assertIn("fournisseur", sans.html(sans.article("probleme"), "#000000"))

    def test_document_imprimable(self):
        service = GuideService(FauxAuth("comptable"))
        articles = service.articles()
        document = service.document(articles, "Collège Test", "#0F766E")
        self.assertIn("Collège Test", document)
        self.assertEqual(document.count("page-break-before"), len(articles))
        for a in articles:
            self.assertIn(html.escape(a.titre), document)
        self.assertIn("EduPaie", service.document(articles, "", "#000000"))

    def test_rendu_de_la_liste_de_demarrage(self):
        etapes = [
            {"id": "a", "titre": "Étape A", "detail": "Détail A", "fait": True,
             "facultatif": False, "ecran": "classes", "article": "classes"},
            {"id": "b", "titre": "Étape B", "detail": "Détail B", "fait": False,
             "facultatif": False, "ecran": "frais", "article": None},
            {"id": "c", "titre": "Étape C", "detail": "Détail C", "fait": False,
             "facultatif": True, "ecran": "frais", "article": "frais"},
        ]
        rendu = GuideService().html_demarrage(etapes, "#0F766E")
        self.assertIn("1 étape(s) sur 2", rendu)  # l'étape facultative ne compte pas
        self.assertIn("(facultatif)", rendu)
        self.assertIn('href="ecran:classes"', rendu)
        self.assertIn('href="guide:classes"', rendu)
        self.assertIn("✔", rendu)
        self.assertIn("○", rendu)


class TestDemarrage(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.repo = DemarrageRepository(self.conn)

    def tearDown(self):
        self.conn.close()

    def service(self, role="admin", ecole="", admins=1, codes=0, sauvegardes=(), mode="essai"):
        sauvegarde = SimpleNamespace(lister=lambda: list(sauvegardes))
        licence = SimpleNamespace(etat=lambda: SimpleNamespace(mode=mode))
        return DemarrageService(self.repo, FauxAuth(role, admins, codes), sauvegarde, licence,
                                ecole=lambda: ParametresEcole(ecole))

    def etapes(self, **options):
        return {e["id"]: e for e in self.service(**options).etapes()}

    def test_ecole_neuve(self):
        etapes = self.etapes()
        self.assertEqual(len(etapes), 10)
        self.assertFalse(any(e["fait"] for e in etapes.values()))
        self.assertEqual([i for i, e in etapes.items() if e["facultatif"]], ["echeancier"])

    def test_les_etapes_se_cochent_d_apres_les_donnees(self):
        ClasseRepository(self.conn).ajouter("6e A")
        FraisRepository(self.conn).ajouter("6e A", "2026-2027", "Scolarité", 100000)
        EcheanceRepository(self.conn).ajouter("6e A", "2026-2027", "T1", "2026-10-15", 100)
        EleveRepository(self.conn).ajouter(Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        utilisateurs = UtilisateurRepository(self.conn)
        utilisateurs.creer("admin", "Administrateur", "x", "admin")
        utilisateurs.creer("caisse", "Caissier", "x", "comptable")
        etapes = self.etapes(ecole="Collège Test", admins=2, codes=8,
                             sauvegardes=[{"motif": "manuelle"}], mode="licence")
        self.assertTrue(all(e["fait"] for e in etapes.values()), etapes)

    def test_cas_particuliers(self):
        etapes = self.etapes(sauvegardes=[{"motif": "auto"}])
        self.assertFalse(etapes["sauvegarde"]["fait"])  # seules les copies manuelles comptent
        UtilisateurRepository(self.conn).creer("admin", "Administrateur", "x", "admin")
        self.assertFalse(self.etapes()["comptes"]["fait"])  # un seul compte : pas encore
        self.assertFalse(self.etapes(admins=1)["admin2"]["fait"])
        self.assertTrue(self.etapes(admins=2)["admin2"]["fait"])
        self.assertFalse(self.etapes(mode="expire")["licence"]["fait"])
        EleveRepository(self.conn).ajouter(Eleve(None, "A", "Un", "5e B", "2026-2027", 1000))
        self.assertTrue(self.etapes()["classes"]["fait"])  # classe présente dans les données

    def test_visibilite(self):
        self.assertTrue(self.service("admin").visible())
        self.assertFalse(self.service("comptable").visible())


if __name__ == "__main__":
    unittest.main()