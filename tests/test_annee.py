import sqlite3
import tempfile
import unittest

from openpyxl import load_workbook

from edupaie.models.entities import Eleve
from edupaie.repositories.annee_repository import AnneeRepository, decaler_date
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.classe_repository import ClasseRepository
from edupaie.repositories.contact_repository import ContactRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services import audit_regles
from edupaie.services.annee_service import (AnneeService, annee_suivante,
                                            proposer_destination, valider_annee)
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.classe_service import ClasseService
from edupaie.services.echeancier_service import EcheancierService
from edupaie.services.export_passage import exporter_passage
from edupaie.services.frais_service import FraisService
from edupaie.services.paiement_service import (TOUTES_LES_ANNEES, ErreurMetier,
                                               PaiementService)
from edupaie.services.remise_service import RemiseService

SOURCE, CIBLE = "2026-2027", "2027-2028"


class TestAnnee(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.eleves = EleveRepository(self.conn)
        self.paiements = PaiementRepository(self.conn)
        self.frais = FraisService(FraisRepository(self.conn))
        self.echeancier = EcheancierService(
            EcheanceRepository(self.conn), self.eleves, self.paiements,
            ContactRepository(self.conn))
        ClasseService(ClasseRepository(self.conn)).ajouter_plusieurs(
            ["6e A", "6e B", "5e A", "5e B"])
        self.annees = AnneeService(AnneeRepository(self.conn), ClasseRepository(self.conn))
        self.paie = PaiementService(self.eleves, self.paiements,
                                    annee_active=self.annees.active)
        self.remises = RemiseService(RemiseRepository(self.conn), self.eleves, self.paiements)
        self.ama = self.eleve("Ama", "6e A", 100000, payer=100000)
        self.kofi = self.eleve("Kofi", "6e A", 100000, payer=40000)
        self.fatou = self.eleve("Fatou", "6e B", 100000, remise=10000)
        self.issouf = self.eleve("Issouf", "5e B", 120000, payer=20000)
        self.frais.ajouter_ligne("5e A", CIBLE, "Scolarité", 110000)
        self.frais.ajouter_ligne("5e B", CIBLE, "Scolarité", 130000)

    def tearDown(self):
        self.conn.close()

    def eleve(self, prenom, classe, total, payer=0, remise=0, annee=SOURCE):
        eleve_id = self.eleves.ajouter(Eleve(None, "Test", prenom, classe, annee, total))
        if payer:
            self.paie.enregistrer_paiement(eleve_id, payer, "2026-09-01", "especes")
        if remise:
            self.remises.accorder(eleve_id, "montant", remise, "Bourse sociale")
        return eleve_id

    def plan(self, **destinations):
        ids = {"Ama": self.ama, "Kofi": self.kofi, "Fatou": self.fatou,
               "Issouf": self.issouf}
        return [{"eleve_id": ids[p], "destination": d, "reinscrire": d is not None}
                for p, d in destinations.items()]

    def nouveaux(self):
        return {e.prenom: e for e in self.eleves.lister("", None)
                if e.annee_scolaire == CIBLE}

    # --- Outils ---------------------------------------------------------------------
    def test_annees(self):
        self.assertEqual(annee_suivante("2026-2027"), "2027-2028")
        self.assertEqual(valider_annee("2026/2027"), "2026-2027")
        for faux in ("2026-2028", "abc", "", None):
            with self.assertRaises(ErreurMetier):
                valider_annee(faux)
        self.assertEqual(decaler_date("2026-10-15", 1), "2027-10-15")
        self.assertEqual(decaler_date("2024-02-29", 1), "2025-02-28")

    def test_destination_proposee(self):
        classes = ["6e A", "6e B", "5e A", "5e B", "4e A"]
        self.assertEqual(proposer_destination(classes, "6e A"), "5e A")
        self.assertEqual(proposer_destination(classes, "6e B"), "5e B")
        self.assertEqual(proposer_destination(classes, "5e B"), "4e A")  # section absente
        self.assertIsNone(proposer_destination(classes, "4e A"))         # dernière classe
        self.assertIsNone(proposer_destination(classes, "7e"))           # classe inconnue
        niveaux = ["6e", "5e", "Tle"]
        self.assertEqual(proposer_destination(niveaux, "6e"), "5e")
        self.assertIsNone(proposer_destination(niveaux, "Tle"))

    def test_proposition(self):
        lignes = {l["prenom"]: l for l in self.annees.proposer(SOURCE)["lignes"]}
        self.assertEqual({p: l["arrieres"] for p, l in lignes.items()},
                         {"Ama": 0, "Kofi": 60000, "Fatou": 90000, "Issouf": 100000})
        self.assertEqual({p: l["destination"] for p, l in lignes.items()},
                         {"Ama": "5e A", "Kofi": "5e A", "Fatou": "5e B", "Issouf": None})
        self.assertTrue(all(l["statut"] == "a_faire" for l in lignes.values()))

    # --- Passage ----------------------------------------------------------------------
    def test_passage_complet(self):
        ContactRepository(self.conn).enregistrer(self.kofi, "M. Kofi", "90 12 34 56")
        r = self.annees.executer(
            SOURCE, self.plan(Ama="5e A", Kofi="5e A", Fatou="5e B", Issouf="5e B"))
        self.assertEqual((r["reinscrits"], r["sortants"], r["arrieres"], r["cible"]),
                         (4, 0, 250000, CIBLE))
        nouveaux = self.nouveaux()
        self.assertEqual({p: e.total_du for p, e in nouveaux.items()},
                         {"Ama": 110000, "Kofi": 170000, "Fatou": 220000, "Issouf": 230000})
        self.assertEqual(nouveaux["Kofi"].classe, "5e A")
        for ancien in (self.ama, self.kofi, self.fatou, self.issouf):
            situation = self.paie.situation(ancien)
            self.assertEqual((situation.solde, situation.statut), (0, "Soldé"))
        self.assertEqual(self.paiements.lister_par_eleve(self.kofi)[0].solde_apres, 0)
        remise = self.remises.lister(self.kofi)[0]
        self.assertEqual(remise["montant"], 60000)
        self.assertIn(CIBLE, remise["motif"])
        self.assertEqual(ContactRepository(self.conn).get(nouveaux["Kofi"].id)["tuteur"],
                         "M. Kofi")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM passage").fetchone()[0], 4)
        self.assertEqual(self.annees.active(), CIBLE)
        self.assertEqual(self.paie.situation(nouveaux["Kofi"].id).solde, 170000)

    def test_frais_non_definis_reprennent_l_ancien_total(self):
        r = self.annees.executer(SOURCE, self.plan(Ama="6e A"))  # redoublement, sans frais
        self.assertEqual(r["sans_frais"], 1)
        self.assertEqual(self.nouveaux()["Ama"].total_du, 100000)

    def test_sortants_gardent_leur_arriere_sur_l_ancienne_fiche(self):
        r = self.annees.executer(
            SOURCE, self.plan(Ama="5e A", Kofi=None, Fatou=None, Issouf=None))
        self.assertEqual((r["reinscrits"], r["sortants"]), (1, 3))
        self.assertEqual(self.paie.situation(self.kofi).solde, 60000)
        self.assertEqual(list(self.nouveaux()), ["Ama"])

    def test_sans_report_des_arrieres(self):
        r = self.annees.executer(SOURCE, self.plan(Kofi="5e A"), reporter_arrieres=False)
        self.assertEqual(r["arrieres"], 0)
        self.assertEqual(self.nouveaux()["Kofi"].total_du, 110000)
        self.assertEqual(self.paie.situation(self.kofi).solde, 60000)
        self.assertEqual(self.remises.lister(self.kofi), [])

    def test_relancer_le_passage_ne_cree_pas_de_doublons(self):
        self.annees.executer(SOURCE, self.plan(Kofi="5e A"))
        with self.assertRaises(ErreurMetier):
            self.annees.executer(SOURCE, self.plan(Kofi="5e A"))
        self.assertEqual(len(self.nouveaux()), 1)
        ligne = next(l for l in self.annees.proposer(SOURCE)["lignes"]
                     if l["prenom"] == "Kofi")
        self.assertEqual(ligne["statut"], "fait")

    def test_un_eleve_deja_inscrit_dans_la_nouvelle_annee_est_ignore(self):
        self.eleves.ajouter(Eleve(None, "Test", "Ama", "5e A", CIBLE, 1000))
        ligne = next(l for l in self.annees.proposer(SOURCE)["lignes"]
                     if l["prenom"] == "Ama")
        self.assertEqual(ligne["statut"], "inscrit")
        with self.assertRaises(ErreurMetier):
            self.annees.executer(SOURCE, self.plan(Ama="5e A"))

    def test_plans_invalides_refuses(self):
        with self.assertRaises(ErreurMetier):
            self.annees.executer(SOURCE, self.plan(Ama="9e Z"))
        ancien = self.eleve("Vieux", "6e A", 1000, annee="2025-2026")
        with self.assertRaises(ErreurMetier):
            self.annees.executer(SOURCE, [{"eleve_id": ancien, "destination": "5e A",
                                           "reinscrire": True}])
        with self.assertRaises(ErreurMetier):
            self.annees.executer(SOURCE, self.plan(Ama=None))  # personne à réinscrire
        self.assertEqual(self.nouveaux(), {})

    def test_le_passage_est_atomique(self):
        bonne = {"eleve_id": self.kofi, "nom": "Test", "prenom": "Kofi",
                 "classe_source": "6e A", "classe_cible": "5e A", "base": 110000,
                 "arrieres": 60000, "total": 170000, "sans_frais": False}
        mauvaise = dict(bonne, eleve_id=self.fatou, nom=None)
        with self.assertRaises(sqlite3.Error):
            AnneeRepository(self.conn).executer_lot(
                [bonne, mauvaise], SOURCE, CIBLE, "Admin", "2026-10-30T10:00:00")
        self.assertEqual(self.nouveaux(), {})
        self.assertEqual(self.remises.lister(self.kofi), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM passage").fetchone()[0], 0)
        self.assertIsNone(self.annees.active())

    def test_sauvegarde_avant_le_passage(self):
        class Fausse:
            def __init__(self, echec=False):
                self.appels, self.echec = [], echec

            def sauvegarder(self, motif="manuelle", dossier=None):
                self.appels.append(motif)
                if self.echec:
                    raise ErreurMetier("disque plein")

        fausse = Fausse()
        service = AnneeService(AnneeRepository(self.conn), ClasseRepository(self.conn),
                               sauvegarde=fausse)
        service.executer(SOURCE, self.plan(Ama="5e A"))
        self.assertEqual(fausse.appels, ["avant-passage"])
        service = AnneeService(AnneeRepository(self.conn), ClasseRepository(self.conn),
                               sauvegarde=Fausse(echec=True))
        with self.assertRaises(ErreurMetier):
            service.executer(SOURCE, self.plan(Kofi="5e A"))
        self.assertEqual(list(self.nouveaux()), ["Ama"])  # Kofi n'a pas été touché

    # --- Frais, année active, droits, rapport ------------------------------------------------
    def test_reprendre_frais_et_echeanciers(self):
        self.frais.ajouter_ligne("6e A", SOURCE, "Inscription", 20000)
        self.frais.ajouter_ligne("6e A", SOURCE, "Scolarité", 80000)
        self.echeancier.ajouter_ligne("6e A", SOURCE, "T1", "2026-10-15", 40)
        self.echeancier.ajouter_ligne("6e A", SOURCE, "T2", "2027-01-15", 60)
        r = self.annees.reprendre_frais(SOURCE)
        self.assertEqual(self.frais.total("6e A", CIBLE), 100000)
        self.assertEqual([l["date_limite"] for l in self.echeancier.lister("6e A", CIBLE)],
                         ["2027-10-15", "2028-01-15"])
        self.assertEqual((r["frais_lignes"], r["echeance_lignes"], r["cible"]),
                         (2, 2, CIBLE))
        self.assertEqual(self.annees.reprendre_frais(SOURCE)["frais_lignes"], 0)  # déjà fait

    def test_annee_active_et_filtres(self):
        def nombre(annee=None):
            return len(self.paie.situations(annee=annee))

        self.assertEqual(nombre(), 4)  # aucune année active : tout est affiché
        self.annees.executer(SOURCE, self.plan(Ama="5e A", Kofi="5e A"))
        self.assertEqual(self.annees.active(), CIBLE)
        self.assertEqual(nombre(), 2)
        self.assertEqual(nombre(TOUTES_LES_ANNEES), 6)
        self.assertEqual(nombre(SOURCE), 4)
        self.assertEqual(self.paie.tableau_de_bord()["nb_eleves"], 2)
        self.annees.definir_active(SOURCE)
        self.assertEqual(nombre(), 4)

    def test_seul_un_admin_gere_les_annees(self):
        utilisateurs = UtilisateurRepository(self.conn)
        auth = AuthService(utilisateurs)
        service = AnneeService(AnneeRepository(self.conn), ClasseRepository(self.conn), auth)
        identifiant = utilisateurs.creer("caisse", "Caissier", "x", "comptable")
        auth.utilisateur = {"id": identifiant, "login": "caisse",
                            "nom_complet": "Caissier", "role": "comptable"}
        for appel in (lambda: service.proposer(SOURCE),
                      lambda: service.executer(SOURCE, self.plan(Ama="5e A")),
                      lambda: service.definir_active(SOURCE),
                      lambda: service.reprendre_frais(SOURCE)):
            with self.assertRaises(ErreurMetier):
                appel()
        self.assertIsNone(service.active())  # la lecture de l'année active reste libre

    def test_rapport_excel_et_journal(self):
        journal = JournalService(JournalRepository(self.conn))
        service = Audite(self.annees, journal, audit_regles.regles_annee())
        r = service.executer(SOURCE, self.plan(Ama="5e A", Kofi="5e A"))
        action = journal.repo.lister("2000-01-01", "2100-01-01")[0]
        self.assertEqual(action["action"], "annee.passage")
        self.assertIn(f"{SOURCE} → {CIBLE}", action["detail"])
        with tempfile.TemporaryDirectory() as tmp:
            feuille = load_workbook(exporter_passage(r, tmp)).active
        self.assertEqual(feuille.title, f"Passage {CIBLE}")
        self.assertEqual(feuille["C2"].value, "5e A")
        self.assertEqual((feuille["A4"].value, feuille["D4"].value, feuille["E4"].value),
                         ("TOTAL", 60000, 280000))


if __name__ == "__main__":
    unittest.main()