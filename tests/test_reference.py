import sqlite3
import unittest
from datetime import datetime

from edupaie import references
import tempfile

from edupaie.models.entities import Eleve, Paiement
from edupaie.services.recu_pdf import generer_recu_pdf
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.rapprochement_repository import RapprochementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.rapprochement_service import ETATS, RapprochementService
from openpyxl import load_workbook

from edupaie.services.caisse_service import CaisseService
from edupaie.services.export_excel import exporter_cloture


class TestReferences(unittest.TestCase):
    def test_nettoyage_et_comparaison(self):
        self.assertIsNone(references.nettoyer("   "))
        self.assertIsNone(references.nettoyer(None))
        self.assertEqual(references.nettoyer("  MP260105   1234 "), "MP260105 1234")
        self.assertEqual(references.normaliser("mp26-0105.1234"), "MP2601051234")
        self.assertEqual(references.normaliser("MP2601051234"), references.normaliser("mp26 0105 1234"))
        for faux in ("abc", "é" * 6, "x" * 41, "ABCD#1234"):
            with self.assertRaises(ValueError, msg=faux):
                references.nettoyer(faux)


class TestPaiementAvecReference(unittest.TestCase):
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
                                 ("kossi", "Kossi Mensah", "comptable")):
            self.comptes[login] = {"id": utilisateurs.creer(login, nom, "x", role),
                                   "login": login, "nom_complet": nom, "role": role}
        eleves = EleveRepository(self.conn)
        self.paie = PaiementService(eleves, PaiementRepository(self.conn), self.auth)
        self.eleve = eleves.ajouter(Eleve(None, "Ama", "A", "6e A", "2026-2027", 500000))
        self.auth.utilisateur = self.comptes["kossi"]

    def tearDown(self):
        self.conn.close()

    def payer(self, montant, mode="mobile_money", reference=None, date="2026-11-03"):
        return self.paie.enregistrer_paiement(self.eleve, montant, date, mode, reference)

    def test_le_numero_est_enregistre(self):
        p = self.payer(10000, reference="  mp-2611.0001 ")
        self.assertEqual(p.reference, "mp-2611.0001")
        self.assertEqual(self.paie.historique(self.eleve)[0].reference, "mp-2611.0001")
        self.assertIsNone(self.payer(5000).reference)  # le numéro reste facultatif

    def test_pas_de_numero_pour_les_especes(self):
        self.assertIsNone(self.payer(5000, "especes", "ABCD1234").reference)

    def test_la_cloture_contient_le_numero(self):
        self.payer(10000, reference="MP-2611-0001")
        self.payer(5000, "especes")
        self.auth.utilisateur = self.comptes["admin"]
        cloture = CaisseService(PaiementRepository(self.conn), self.auth).cloture(
            "2026-11-03", "2026-11-03")
        refs = sorted((p["reference"] or "") for c in cloture["caissiers"]
                      for p in c["paiements"])
        self.assertEqual(refs, ["", "MP-2611-0001"])
        with tempfile.TemporaryDirectory() as tmp:
            classeur = load_workbook(exporter_cloture(cloture, tmp))
            lignes = list(classeur["Détail"].iter_rows(min_row=2, values_only=True))
            self.assertEqual(sorted(l[9] or "" for l in lignes), ["", "MP-2611-0001"])
            classeur.close()

    def test_numero_invalide(self):
        for faux in ("abc", "x" * 41, "AB#12345"):
            with self.assertRaises(ErreurMetier, msg=faux):
                self.payer(5000, reference=faux)

    def test_un_numero_ne_sert_qu_une_fois(self):
        p = self.payer(10000, reference="MP-12345")
        with self.assertRaises(ErreurMetier) as contexte:
            self.payer(5000, reference="mp 12345")  # même numéro, autre écriture
        self.assertIn("déjà enregistré", str(contexte.exception))
        self.payer(5000, "virement", "MP-12345")  # un autre mode n'est pas concerné
        self.auth.utilisateur = self.comptes["admin"]
        self.paie.annuler_paiement(p.id, "Erreur de saisie")
        self.auth.utilisateur = self.comptes["kossi"]
        self.assertEqual(self.payer(10000, reference="MP-12345").reference, "MP-12345")

    def test_le_rapprochement_exact_par_numero(self):
        pa = self.payer(10000, reference="TXA-111")
        pb = self.payer(10000, reference="TXB-222")  # même montant, même jour
        pc = self.payer(20000, date="2026-11-04", reference="TXC333")
        pd = self.payer(7000, date="2026-11-04", reference="TXD444")
        pe = self.payer(5000, date="2026-11-04")  # sans numéro
        service = RapprochementService(RapprochementRepository(self.conn), None,
                                       maintenant=lambda: datetime(2026, 11, 5, 9, 0))
        service.importer([
            {"date": "2026-11-03", "montant": 10000, "reference": "txb222", "libelle": ""},
            {"date": "2026-11-03", "montant": 10000, "reference": "TXA 111", "libelle": ""},
            {"date": "2026-11-04", "montant": 25000, "reference": "TXC333", "libelle": ""},
            {"date": "2026-11-04", "montant": 7000, "reference": "TXZ999", "libelle": ""},
            {"date": "2026-11-04", "montant": 5000, "reference": "TXE555", "libelle": ""}], "Flooz")

        a = service.analyser("2026-11-03", "2026-11-04")
        lignes = {l["reference"]: l for l in a["lignes"]}
        # deux paiements identiques ne se confondent plus : le numéro les départage
        self.assertEqual(lignes["txb222"]["etat"], "propose_ref")
        self.assertEqual(lignes["txb222"]["proposition"]["paiement_id"], pb.id)
        self.assertEqual(lignes["TXA 111"]["etat"], "propose_ref")
        self.assertEqual(lignes["TXA 111"]["proposition"]["paiement_id"], pa.id)
        # même numéro, montant différent : anomalie
        self.assertEqual(lignes["TXC333"]["etat"], "ecart")
        self.assertEqual(lignes["TXC333"]["proposition"]["paiement_id"], pc.id)
        # deux numéros différents : jamais rapprochés, même au même montant
        self.assertEqual(lignes["TXZ999"]["etat"], "sans_paiement")
        # un paiement sans numéro se rapproche toujours par montant et date
        self.assertEqual(lignes["TXE555"]["etat"], "propose_sur")
        self.assertEqual(lignes["TXE555"]["proposition"]["paiement_id"], pe.id)
        self.assertEqual([p["id"] for p in a["sans_trace"]], [pd.id])
        self.assertEqual(a["sans_trace"][0]["reference"], "TXD444")
        self.assertEqual((a["resume"]["nb_propose"], a["resume"]["nb_sans_paiement"],
                          a["resume"]["montant_sans_paiement"]), (3, 2, 32000))
        self.assertIn("n° de transaction", ETATS["propose_ref"])

        # refus manuels
        with self.assertRaises(ErreurMetier) as contexte:
            service.rapprocher(lignes["TXC333"]["id"], pc.id)
        self.assertIn("montants", str(contexte.exception))
        with self.assertRaises(ErreurMetier) as contexte:
            service.rapprocher(lignes["TXZ999"]["id"], pd.id)
        self.assertIn("numéros de transaction", str(contexte.exception))
        self.assertEqual(service.candidats(lignes["TXZ999"]["id"]), [])

        # le rapprochement automatique lie les correspondances exactes et sûres
        self.assertEqual(service.rapprocher_automatiquement("2026-11-03", "2026-11-04"),
                         {"rapproches": 3})
        etats = {l["reference"]: l["etat"] for l in service.analyser(
            "2026-11-03", "2026-11-04")["lignes"]}
        self.assertEqual([etats[r] for r in ("txb222", "TXA 111", "TXE555")],
                         ["rapproche"] * 3)
        self.assertEqual((etats["TXC333"], etats["TXZ999"]), ("ecart", "sans_paiement"))

class TestRecuAvecReference(unittest.TestCase):
    def test_le_recu_se_genere_avec_ou_sans_numero(self):
        eleve = Eleve(1, "Ama", "Ayivi", "6e A", "2026-2027", 100000)
        cas = (("mobile_money", "MP260105.1234.A1B2"), ("mobile_money", "M" * 40),
               ("cheque", "CHQ-0042"), ("virement", "VIR 2026 11 03"),
               ("especes", None), ("mobile_money", None))
        with tempfile.TemporaryDirectory() as tmp:
            for i, (mode, reference) in enumerate(cas, start=1):
                paiement = Paiement(i, 1, f"REC-2026-{i:06d}", 10000, "2026-11-03", mode,
                                    90000, None, "Kossi Mensah", reference=reference)
                chemin = generer_recu_pdf(eleve, paiement, tmp)
                self.assertTrue(chemin.exists(), mode)
                self.assertGreater(chemin.stat().st_size, 1000)

if __name__ == "__main__":
    unittest.main()