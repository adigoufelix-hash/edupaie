import sqlite3
import tempfile
import unittest
from datetime import date

from openpyxl import load_workbook

from edupaie.models.entities import Eleve
from edupaie.permissions import a_permission
from edupaie.repositories.classe_repository import ClasseRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.recouvrement_repository import RecouvrementRepository
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.export_recouvrement import exporter_recouvrement
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.recouvrement_service import RecouvrementService, libelle_mois

ANNEE = "2026-2027"
REF = "2026-11-05"


class FauxAuth:
    def __init__(self, role):
        self.role = role

    def peut(self, permission):
        return a_permission(self.role, permission)


class TestRecouvrement(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        utilisateurs = UtilisateurRepository(self.conn)
        auth = AuthService(utilisateurs)
        comptes = {}
        for login, nom, role in (("admin", "Administrateur", "admin"),
                                 ("kossi", "Kossi Mensah", "comptable")):
            comptes[login] = {"id": utilisateurs.creer(login, nom, "x", role),
                              "login": login, "nom_complet": nom, "role": role}
        classes = ClasseRepository(self.conn)
        classes.ajouter("6e A")
        classes.ajouter("5e B")
        eleves = EleveRepository(self.conn)
        remises = RemiseRepository(self.conn)
        paie = PaiementService(eleves, PaiementRepository(self.conn), auth)
        echeances = EcheanceRepository(self.conn)
        for libelle, limite, pourcentage in (("T1", "2026-10-15", 40), ("T2", "2026-12-15", 30),
                                             ("T3", "2027-03-15", 30)):
            echeances.ajouter("6e A", ANNEE, libelle, limite, pourcentage)

        ama = eleves.ajouter(Eleve(None, "Ama", "A", "6e A", ANNEE, 100000))
        bob = eleves.ajouter(Eleve(None, "Bob", "B", "6e A", ANNEE, 100000))
        cleo = eleves.ajouter(Eleve(None, "Cléo", "C", "6e A", ANNEE, 100000))
        dan = eleves.ajouter(Eleve(None, "Dan", "D", "5e B", ANNEE, 50000))
        eleves.ajouter(Eleve(None, "Eve", "E", "6e A", "2025-2026", 80000))
        remises.ajouter(cleo, "montant", 20000, 20000, "Bourse", "Administrateur",
                        "2026-09-01T09:00:00")

        auth.utilisateur = comptes["kossi"]
        paie.enregistrer_paiement(bob, 100000, "2026-09-20", "especes")
        paie.enregistrer_paiement(ama, 40000, "2026-10-05", "especes")
        erreur = paie.enregistrer_paiement(ama, 5000, "2026-10-06", "mobile_money")
        paie.enregistrer_paiement(cleo, 10000, "2026-11-03", "cheque")
        paie.enregistrer_paiement(dan, 25000, "2026-11-02", "virement")
        auth.utilisateur = comptes["admin"]
        paie.annuler_paiement(erreur.id, "Erreur de saisie")  # ne doit rien compter

        self.repo = RecouvrementRepository(self.conn)
        self.service = RecouvrementService(self.repo, None, aujourdhui=lambda: date(2026, 11, 5))

    def tearDown(self):
        self.conn.close()

    def test_situation_par_classe(self):
        t = self.service.tableau(ANNEE, REF)
        classes = {c["classe"]: c for c in t["classes"]}
        a = classes["6e A"]
        self.assertEqual((a["eleves"], a["total_du"], a["remises"], a["net"]),
                         (3, 300000, 20000, 280000))
        self.assertEqual((a["paye"], a["reste"]), (150000, 130000))
        self.assertEqual(round(a["taux"], 1), 53.6)
        # Au 5 novembre, seule la tranche T1 (40 %) est échue
        self.assertEqual((a["exigible"], a["retard"], a["en_retard"]), (112000, 22000, 1))
        self.assertEqual(round(a["taux_exigible"], 1), 80.4)
        self.assertEqual((a["soldes"], a["partiels"], a["non_payes"]), (1, 2, 0))
        b = classes["5e B"]
        self.assertEqual((b["net"], b["paye"], b["reste"], round(b["taux"], 1)),
                         (50000, 25000, 25000, 50.0))
        self.assertFalse(b["suivi"])  # pas d'échéancier : ni prévu ni retard
        self.assertEqual((b["exigible"], b["retard"]), (0, 0))
        self.assertEqual(t["classes_sans_echeancier"], ["5e B"])
        self.assertEqual([c["classe"] for c in t["classes"]], ["6e A", "5e B"])  # ordre des classes

    def test_total_de_l_ecole(self):
        total = self.service.tableau(ANNEE, REF)["total"]
        self.assertEqual((total["eleves"], total["total_du"], total["remises"], total["net"]),
                         (4, 350000, 20000, 330000))
        self.assertEqual((total["paye"], total["reste"]), (175000, 155000))
        self.assertEqual(round(total["taux"], 1), 53.0)
        self.assertEqual((total["exigible"], total["retard"], total["en_retard"]),
                         (112000, 22000, 1))
        self.assertEqual((total["soldes"], total["partiels"], total["non_payes"]), (1, 3, 0))

    def test_le_retard_change_avec_la_date(self):
        # Le 1er septembre : aucune tranche échue, donc rien d'exigible
        avant = self.service.tableau(ANNEE, "2026-09-01")["total"]
        self.assertEqual((avant["exigible"], avant["retard"]), (0, 0))
        self.assertIsNone(avant["taux_exigible"])
        # Le 1er avril 2027 : tout est échu, le retard est le reste à payer des classes suivies
        apres = self.service.tableau(ANNEE, "2027-04-01")["total"]
        self.assertEqual(apres["exigible"], 280000)
        self.assertEqual(apres["retard"], 130000)
        self.assertEqual(apres["en_retard"], 2)

    def test_evolution_par_mois(self):
        mois = {m["mois"]: m for m in self.service.tableau(ANNEE, REF)["mois"]}
        self.assertEqual(list(mois), ["2026-09", "2026-10", "2026-11", "2026-12", "2027-03"])
        sept, octo, nov = mois["2026-09"], mois["2026-10"], mois["2026-11"]
        self.assertEqual((sept["encaisse"], sept["prevu"], sept["taux"]), (100000, 0, None))
        self.assertEqual((octo["encaisse"], octo["prevu"]), (40000, 112000))  # annulé exclu
        self.assertEqual(round(octo["taux"], 1), 35.7)
        self.assertEqual((octo["cumul_encaisse"], octo["cumul_prevu"]), (140000, 112000))
        self.assertEqual(round(octo["taux_cumule"], 1), 125.0)
        self.assertEqual((nov["encaisse"], nov["prevu"], nov["en_cours"]), (35000, 0, True))
        for futur in ("2026-12", "2027-03"):
            self.assertTrue(mois[futur]["a_venir"])
            self.assertIsNone(mois[futur]["taux"])
        self.assertEqual(mois["2026-12"]["prevu"], 84000)
        self.assertEqual(mois["2027-03"]["cumul_prevu"], 280000)

    def test_annees_et_cas_limites(self):
        self.assertEqual(self.service.annees(), ["2026-2027", "2025-2026"])
        ancienne = self.service.tableau("2025-2026", REF)
        self.assertEqual([c["classe"] for c in ancienne["classes"]], ["6e A"])
        self.assertEqual((ancienne["total"]["paye"], ancienne["total"]["reste"]), (0, 80000))
        self.assertEqual(ancienne["total"]["taux"], 0.0)
        self.assertEqual(ancienne["total"]["non_payes"], 1)
        self.assertEqual(ancienne["classes_sans_echeancier"], ["6e A"])
        vide = self.service.tableau("1999-2000", REF)
        self.assertEqual((vide["classes"], vide["mois"]), ([], []))
        self.assertIsNone(vide["total"]["taux"])
        with self.assertRaises(ErreurMetier):
            self.service.tableau(ANNEE, "pas une date")
        self.assertEqual(self.service.tableau(ANNEE)["date_ref"], REF)  # date du jour injectée

    def test_reserve_a_l_administrateur(self):
        for role in ("comptable", "lecture"):
            service = RecouvrementService(self.repo, FauxAuth(role))
            with self.assertRaises(ErreurMetier):
                service.tableau(ANNEE, REF)
            with self.assertRaises(ErreurMetier):
                service.annees()
        admin = RecouvrementService(self.repo, FauxAuth("admin"))
        self.assertEqual(admin.tableau(ANNEE, REF)["total"]["eleves"], 4)

    def test_libelle_du_mois(self):
        self.assertEqual(libelle_mois("2026-10"), "octobre 2026")
        self.assertEqual(libelle_mois("2027-02"), "février 2027")
        self.assertEqual(libelle_mois("2026-12"), "décembre 2026")

    def test_export_excel(self):
        tableau = self.service.tableau(ANNEE, REF)
        with tempfile.TemporaryDirectory() as tmp:
            chemin = exporter_recouvrement(tableau, tmp)
            classeur = load_workbook(chemin)
            self.assertEqual(classeur.sheetnames, ["Par classe", "Par mois"])
            lignes = {r[0]: r for r in classeur["Par classe"].iter_rows(
                min_row=2, values_only=True)}
            self.assertEqual(lignes["6e A"][1], 3)
            self.assertEqual(lignes["6e A"][5], 150000)
            self.assertEqual(lignes["TOTAL"][5], 175000)
            self.assertEqual(lignes["TOTAL"][9], 22000)
            mois = {r[0]: r for r in classeur["Par mois"].iter_rows(
                min_row=2, values_only=True)}
            self.assertEqual(mois["octobre 2026"][1], 40000)
            self.assertEqual(mois["octobre 2026"][2], 112000)
            classeur.close()


if __name__ == "__main__":
    unittest.main()