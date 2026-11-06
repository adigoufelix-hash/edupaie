import sqlite3
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

from edupaie.models.entities import Eleve
from edupaie.permissions import a_permission
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.rapprochement_repository import RapprochementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services import audit_regles, releve_import
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.export_rapprochement import exporter_rapprochement
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.rapprochement_service import ETATS, RapprochementService

DEBUT, FIN = "2026-11-02", "2026-11-05"
LIGNES = [
    {"date": "2026-11-02", "montant": 25000, "reference": "TX1", "libelle": "Kossi"},
    {"date": "2026-11-03", "montant": 10000, "reference": "TX2", "libelle": "Parent A"},
    {"date": "2026-11-03", "montant": 10000, "reference": "TX3", "libelle": "Parent B"},
    {"date": "2026-11-04", "montant": 50000, "reference": "TX4", "libelle": "Inconnu"},
]


def nouvelle_base():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open("data/schema.sql", encoding="utf-8") as f:
        conn.executescript(f.read())
    return conn


class FauxAuth:
    def __init__(self, role):
        self.role = role

    def peut(self, permission):
        return a_permission(self.role, permission)


class TestLectureDuReleve(unittest.TestCase):
    def test_montants(self):
        attendus = [(25000, 25000), (25000.0, 25000), ("25 000", 25000), ("25\u00a0000 FCFA", 25000),
                    ("25.000", 25000), ("25,000", 25000), ("1 250,50", 1251), ("1,250.50", 1251),
                    ("12 500F", 12500), ("-5000", -5000), ("abc", None), ("", None),
                    (None, None), (True, None)]
        for valeur, attendu in attendus:
            self.assertEqual(releve_import.lire_montant(valeur), attendu, repr(valeur))

    def test_dates(self):
        serial = (date(2026, 11, 2) - date(1899, 12, 30)).days
        for valeur in (datetime(2026, 11, 2, 10, 30), date(2026, 11, 2), "02/11/2026",
                       "02/11/2026 14:05", "2026-11-02 14:05:33", "2-11-26", serial):
            self.assertEqual(releve_import.lire_date(valeur), "2026-11-02", repr(valeur))
        for valeur in ("31/02/2026", "n'importe quoi", "", None, 12):
            self.assertIsNone(releve_import.lire_date(valeur), repr(valeur))

    def test_detection_des_colonnes(self):
        entetes = ["Date", "Numéro de transaction", "Type", "Expéditeur", "Débit", "Crédit", "Solde"]
        trouve = releve_import.detecter_colonnes(entetes)
        self.assertEqual(trouve, {"date": 0, "montant": 5, "reference": 1, "libelle": 3, "sens": 2})
        trouve = releve_import.detecter_colonnes(["Date opération", "Montant (FCFA)", "Référence", "Nom"])
        self.assertEqual(trouve, {"date": 0, "montant": 1, "reference": 2, "libelle": 3, "sens": None})

    def test_ligne_des_titres(self):
        lignes = [["Relevé Flooz", None, None], ["Période", "01/11", "05/11"],
                  ["Date", "Montant", "Référence"], ["02/11/2026", "25 000", "TX1"]]
        self.assertEqual(releve_import.trouver_entete(lignes), 2)
        self.assertEqual(releve_import.trouver_entete([["a", "b"], ["c", "d"]]), 0)

    def test_normalisation(self):
        lignes = [["Date", "Type", "Montant", "Réf", "Nom"],
                  ["02/11/2026", "Crédit", "25 000", "TX1", "Kossi"],
                  ["03/11/2026", "Débit", "10 000", "TX2", "Frais"],
                  ["pas une date", "Crédit", "5 000", "TX3", "X"],
                  ["04/11/2026", "Crédit", "-5 000", "TX4", "Y"],
                  [None, None, None, None, None],
                  ["05/11/2026", "Crédit", 12500.0, 1234567.0, "  Ama   D  "]]
        colonnes = {"date": 0, "sens": 1, "montant": 2, "reference": 3, "libelle": 4}
        valides, ecartees = releve_import.normaliser(lignes, colonnes, 1, "credit")
        self.assertEqual(valides, [
            {"date": "2026-11-02", "montant": 25000, "reference": "TX1", "libelle": "Kossi"},
            {"date": "2026-11-05", "montant": 12500, "reference": "1234567", "libelle": "Ama D"}])
        self.assertEqual([n for n, _ in ecartees], [3, 4, 5])
        self.assertIn("ignoré", ecartees[0][1])
        self.assertIn("date", ecartees[1][1])
        self.assertIn("montant", ecartees[2][1])

    def test_fichiers_csv_et_excel(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_ = Path(tmp) / "releve.csv"
            csv_.write_bytes("Date;Montant;Libellé\n02/11/2026;25 000;Kossi\n".encode("cp1252"))
            self.assertEqual(releve_import.lire_tableau(csv_),
                             [["Date", "Montant", "Libellé"], ["02/11/2026", "25 000", "Kossi"]])
            xlsx = Path(tmp) / "releve.xlsx"
            classeur = Workbook()
            classeur.active.append(["Date", "Montant"])
            classeur.active.append([datetime(2026, 11, 2), 25000])
            classeur.save(xlsx)
            lignes = releve_import.lire_tableau(xlsx)
            self.assertEqual(lignes[1], [datetime(2026, 11, 2), 25000])
            ancien = Path(tmp) / "releve.xls"
            ancien.write_bytes(b"x")
            with self.assertRaises(ErreurMetier):
                releve_import.lire_tableau(ancien)


class TestRapprochement(unittest.TestCase):
    def setUp(self):
        self.conn = nouvelle_base()
        utilisateurs = UtilisateurRepository(self.conn)
        self.auth = AuthService(utilisateurs)
        self.comptes = {}
        for login, nom, role in (("admin", "Administrateur", "admin"),
                                 ("kossi", "Kossi Mensah", "comptable")):
            self.comptes[login] = {"id": utilisateurs.creer(login, nom, "x", role),
                                   "login": login, "nom_complet": nom, "role": role}
        eleves = EleveRepository(self.conn)
        self.paie = PaiementService(eleves, PaiementRepository(self.conn), self.auth)
        ama, bob, cleo, dan = (eleves.ajouter(Eleve(None, nom, "X", "6e A", "2026-2027", 100000))
                               for nom in ("Ama", "Bob", "Cléo", "Dan"))
        self.auth.utilisateur = self.comptes["kossi"]
        self.p1 = self.paie.enregistrer_paiement(ama, 25000, "2026-11-02", "mobile_money")
        self.p2 = self.paie.enregistrer_paiement(bob, 10000, "2026-11-03", "mobile_money")
        self.p3 = self.paie.enregistrer_paiement(cleo, 10000, "2026-11-03", "mobile_money")
        self.p4 = self.paie.enregistrer_paiement(dan, 15000, "2026-11-04", "mobile_money")
        self.p5 = self.paie.enregistrer_paiement(ama, 8000, "2026-11-02", "especes")
        self.p6 = self.paie.enregistrer_paiement(bob, 5000, "2026-11-04", "mobile_money")
        self.auth.utilisateur = self.comptes["admin"]
        self.paie.annuler_paiement(self.p6.id, "Erreur de saisie")

        self.service = RapprochementService(
            RapprochementRepository(self.conn), None, maintenant=lambda: datetime(2026, 11, 5, 9, 0))
        self.service.importer(LIGNES, "Flooz")

    def tearDown(self):
        self.conn.close()

    def analyse(self, debut=DEBUT, fin=FIN):
        a = self.service.analyser(debut, fin)
        return a, {l["reference"]: l for l in a["lignes"]}

    def test_analyse_initiale(self):
        a, l = self.analyse()
        self.assertEqual(l["TX1"]["etat"], "propose_sur")
        self.assertEqual(l["TX1"]["proposition"]["paiement_id"], self.p1.id)
        self.assertEqual((l["TX2"]["etat"], l["TX3"]["etat"]),
                         ("propose_probable", "propose_probable"))
        self.assertEqual(l["TX2"]["proposition"]["paiement_id"], self.p2.id)
        self.assertEqual(l["TX3"]["proposition"]["paiement_id"], self.p3.id)
        self.assertEqual(l["TX2"]["proposition"]["alternatives"], 1)
        self.assertEqual(l["TX4"]["etat"], "sans_paiement")
        # P5 (espèces) et P6 (annulé) n'ont rien à faire ici ; P4 n'a aucune trace
        self.assertEqual([p["id"] for p in a["sans_trace"]], [self.p4.id])
        r = a["resume"]
        self.assertEqual((r["nb_lignes"], r["montant_releve"]), (4, 95000))
        self.assertEqual((r["nb_rapproche"], r["montant_rapproche"], r["ecart"]), (0, 0, 95000))
        self.assertEqual((r["nb_propose"], r["nb_sans_paiement"], r["montant_sans_paiement"]),
                         (3, 1, 50000))
        self.assertEqual((r["nb_sans_trace"], r["montant_sans_trace"]), (1, 15000))
        self.assertEqual((r["nb_enregistre"], r["montant_enregistre"]), (4, 60000))

    def test_rapprochement_automatique_puis_manuel(self):
        self.assertEqual(self.service.rapprocher_automatiquement(DEBUT, FIN), {"rapproches": 1})
        a, l = self.analyse()
        self.assertEqual(l["TX1"]["etat"], "rapproche")
        self.assertEqual(l["TX1"]["paiement"]["id"], self.p1.id)
        self.assertEqual(l["TX2"]["etat"], "propose_probable")  # jamais automatique
        # refus : montant différent, espèces, annulé
        for faux in (self.p4, self.p5, self.p6):
            with self.assertRaises(ErreurMetier):
                self.service.rapprocher(l["TX3"]["id"], faux.id)
        r = self.service.rapprocher(l["TX2"]["id"], self.p2.id)
        self.assertEqual((r["montant"], r["date"]), (10000, "2026-11-03"))
        self.assertTrue(r["numero_recu"].startswith("REC-"))
        with self.assertRaises(ErreurMetier):  # P2 est déjà rapproché
            self.service.rapprocher(l["TX3"]["id"], self.p2.id)
        with self.assertRaises(ErreurMetier):  # TX2 est déjà traitée
            self.service.rapprocher(l["TX2"]["id"], self.p3.id)
        self.service.rapprocher(l["TX3"]["id"], self.p3.id)
        a, l = self.analyse()
        self.assertEqual([l[r]["etat"] for r in ("TX1", "TX2", "TX3", "TX4")],
                         ["rapproche", "rapproche", "rapproche", "sans_paiement"])
        self.assertEqual((a["resume"]["nb_rapproche"], a["resume"]["montant_rapproche"]), (3, 45000))

    def test_ignorer_et_defaire(self):
        self.service.rapprocher_automatiquement(DEBUT, FIN)
        a, l = self.analyse()
        with self.assertRaises(ErreurMetier):
            self.service.ignorer(l["TX4"]["id"], "ok")  # motif trop court
        r = self.service.ignorer(l["TX4"]["id"], "Virement personnel du directeur")
        self.assertEqual((r["montant"], r["motif"]), (50000, "Virement personnel du directeur"))
        a, l = self.analyse()
        self.assertEqual(l["TX4"]["etat"], "ignore")
        self.assertEqual(a["resume"]["montant_releve"], 45000)  # l'opération ignorée sort du total
        self.assertEqual((a["resume"]["nb_ignore"], a["resume"]["montant_ignore"]), (1, 50000))
        with self.assertRaises(ErreurMetier):
            self.service.ignorer(l["TX4"]["id"], "Deuxième tentative")
        # annuler un rapprochement libère le paiement
        self.service.defaire(l["TX1"]["id"])
        a, l = self.analyse()
        self.assertEqual((l["TX1"]["etat"], l["TX1"]["proposition"]["paiement_id"]),
                         ("propose_sur", self.p1.id))
        self.service.defaire(l["TX4"]["id"])
        with self.assertRaises(ErreurMetier):
            self.service.defaire(l["TX4"]["id"])  # déjà à traiter

    def test_alerte_si_le_paiement_est_annule_apres_coup(self):
        self.service.rapprocher_automatiquement(DEBUT, FIN)
        self.paie.annuler_paiement(self.p1.id, "Erreur de saisie")
        a, l = self.analyse()
        self.assertEqual(l["TX1"]["etat"], "alerte")
        self.assertTrue(l["TX1"]["paiement"]["annule"])
        self.assertEqual(a["resume"]["nb_alertes"], 1)
        self.assertNotIn(self.p1.id, [p["id"] for p in a["sans_trace"]])

    def test_tolerance_de_date(self):
        self.service.importer([
            {"date": "2026-11-06", "montant": 15000, "reference": "TX5", "libelle": ""},
            {"date": "2026-11-09", "montant": 15000, "reference": "TX6", "libelle": ""}], "Flooz")
        a, l = self.analyse(DEBUT, "2026-11-09")
        self.assertEqual(l["TX5"]["etat"], "propose_sur")  # 2 jours après P4 : accepté
        self.assertEqual(l["TX6"]["etat"], "sans_paiement")  # 5 jours : refusé

    def test_choix_manuel(self):
        a, l = self.analyse()
        self.assertEqual([c["id"] for c in self.service.candidats(l["TX2"]["id"])],
                         [self.p2.id, self.p3.id])
        self.assertEqual(self.service.candidats(l["TX4"]["id"]), [])
        self.service.rapprocher(l["TX2"]["id"], self.p2.id)
        self.assertEqual([c["id"] for c in self.service.candidats(l["TX3"]["id"])], [self.p3.id])
        with self.assertRaises(ErreurMetier):
            self.service.candidats(l["TX2"]["id"])  # déjà traitée

    def test_reimporter_le_meme_releve(self):
        r = self.service.importer(LIGNES, "Flooz")
        self.assertEqual((r["importees"], r["doublons"]), (0, 4))
        sans_reference = [{"date": "2026-11-05", "montant": 7000, "reference": None,
                           "libelle": "Zoé"}] * 2  # deux opérations identiques
        self.assertEqual(self.service.importer(sans_reference, "Flooz")["importees"], 2)
        self.assertEqual(self.service.importer(sans_reference, "Flooz")["doublons"], 2)
        self.assertEqual(self.service.importer(LIGNES, "T-Money")["importees"], 4)  # autre opérateur
        with self.assertRaises(ErreurMetier):
            self.service.importer([], "Flooz")

    def test_periodes(self):
        self.assertEqual(self.service.periode_par_defaut(), ("2026-11-02", "2026-11-04"))
        vide = RapprochementService(RapprochementRepository(nouvelle_base()), None,
                                    maintenant=lambda: datetime(2026, 11, 5, 9, 0))
        self.assertEqual(vide.periode_par_defaut(), ("2026-11-01", "2026-11-05"))
        for debut, fin in (("2026-11-05", "2026-11-02"), ("abc", FIN)):
            with self.assertRaises(ErreurMetier):
                self.service.analyser(debut, fin)

    def test_reserve_a_l_administrateur(self):
        for role in ("comptable", "lecture"):
            service = RapprochementService(RapprochementRepository(self.conn), FauxAuth(role))
            for appel in (lambda: service.importer(LIGNES, "Flooz"),
                          lambda: service.analyser(DEBUT, FIN), lambda: service.rapprocher(1, 1),
                          lambda: service.periode_par_defaut(),
                          lambda: service.rapprocher_automatiquement(DEBUT, FIN)):
                with self.assertRaises(ErreurMetier):
                    appel()
        admin = RapprochementService(RapprochementRepository(self.conn), FauxAuth("admin"))
        self.assertEqual(admin.analyser(DEBUT, FIN)["resume"]["nb_lignes"], 4)

    def test_export_excel(self):
        a, _ = self.analyse()
        with tempfile.TemporaryDirectory() as tmp:
            classeur = load_workbook(exporter_rapprochement(a, tmp))
            self.assertEqual(classeur.sheetnames, ["Relevé", "Sans trace", "Résumé"])
            lignes = {r[2]: r for r in classeur["Relevé"].iter_rows(min_row=2, values_only=True)}
            self.assertEqual(lignes["TX1"][4], ETATS["propose_sur"])
            self.assertEqual(lignes["TX4"][4], ETATS["sans_paiement"])
            self.assertEqual(lignes["TX1"][1], 25000)
            sans = list(classeur["Sans trace"].iter_rows(min_row=2, values_only=True))
            self.assertEqual([r[2] for r in sans], [15000])
            resume = {r[0]: r[1] for r in classeur["Résumé"].iter_rows(min_row=2, values_only=True)}
            self.assertEqual(resume["Écart (relevé non rapproché)"], 95000)
            self.assertEqual(resume["Paiements mobile money sans trace sur le relevé"], 1)
            classeur.close()

    def test_le_journal_ne_garde_que_des_totaux(self):
        self.auth.utilisateur = self.comptes["admin"]
        journal = JournalService(JournalRepository(self.conn), self.auth)
        service = Audite(self.service, journal, audit_regles.regles_rapprochement())
        service.importer(LIGNES, "Flooz")
        service.rapprocher_automatiquement(DEBUT, FIN)
        a, l = self.analyse()
        service.ignorer(l["TX4"]["id"], "Virement personnel")
        service.defaire(l["TX4"]["id"])
        with self.assertRaises(ErreurMetier):
            service.ignorer(l["TX4"]["id"], "xx")  # refusé : rien n'est journalisé
        lignes = journal.repo.lister("2000-01-01", "2100-01-01")
        self.assertEqual([x["action"] for x in lignes], [
            "rapprochement.defaire", "rapprochement.ignore", "rapprochement.auto",
            "rapprochement.import"])
        self.assertIn("0 opération(s), 4 déjà présente(s)", lignes[3]["detail"])
        for ligne in lignes:
            for secret in ("TX1", "Kossi", "Parent A", "Inconnu"):
                self.assertNotIn(secret, ligne["detail"])


if __name__ == "__main__":
    unittest.main()