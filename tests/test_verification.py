import sqlite3
import tempfile
import unittest

from fpdf import FPDF

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.verification_repository import VerificationRepository
from edupaie.services import verification
from edupaie.services.ecole import ParametresEcole
from edupaie.services.paiement_service import PaiementService
from edupaie.services.pdf_commun import dessiner_qr
from edupaie.services.recu_pdf import generer_recu_pdf
from edupaie.services.verification_service import VerificationService


class TestVerification(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.service = VerificationService(VerificationRepository(self.conn))
        verification.definir_cle(self.service.cle())
        eleves, paiements = EleveRepository(self.conn), PaiementRepository(self.conn)
        self.eleve = eleves.ajouter(Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        self.paiement = PaiementService(eleves, paiements).enregistrer_paiement(
            self.eleve, 40000, "2026-09-01", "especes")
        self.numero = self.paiement.numero_recu
        self.qr = verification.contenu_qr(self.paiement)
        self.code = verification.code_pour(self.paiement)

    def tearDown(self):
        verification.definir_cle(None)
        self.conn.close()

    def test_la_cle_est_creee_une_seule_fois(self):
        cle = self.service.cle()
        self.assertEqual(len(cle), 64)
        autre = VerificationService(VerificationRepository(self.conn))
        self.assertEqual(autre.cle(), cle)

    def test_le_code_depend_des_donnees(self):
        base = ("REC-2026-000001", 40000, "2026-09-01", "especes", 1)
        code = verification.calculer_code("cle", *base)
        self.assertEqual(code, verification.calculer_code("cle", *base))
        self.assertEqual(len(code), 10)
        self.assertNotEqual(code, verification.calculer_code("autre", *base))
        for i, valeur in enumerate((40001, "2026-09-02", "cheque", 2), start=1):
            modifie = list(base)
            modifie[i] = valeur
            self.assertNotEqual(code, verification.calculer_code("cle", *modifie))

    def test_le_qr_se_relit(self):
        self.assertTrue(self.qr.startswith("EDUPAIE"))
        self.assertTrue(self.qr.isalnum())
        self.assertEqual(verification.lire_saisie(self.qr), (self.numero, self.code))

    def test_saisies_tolerantes(self):
        self.assertEqual(verification.lire_saisie("rec-2026-000001 a1b2c-3d4e5"),
                         ("REC-2026-000001", "A1B2C3D4E5"))
        self.assertEqual(verification.lire_saisie("REC-2026-000001"),
                         ("REC-2026-000001", None))
        for illisible in ("n'importe quoi", "", None, "REC-26-1"):
            self.assertEqual(verification.lire_saisie(illisible), (None, None))

    def test_recu_authentique(self):
        for saisie in (self.qr, f"{self.numero} {verification.formater_code(self.code)}"):
            resultat = self.service.verifier(saisie)
            self.assertEqual(resultat["statut"], "authentique")
            self.assertEqual(resultat["details"]["eleve"], "A Un")
            self.assertEqual(resultat["details"]["montant"], 40000)

    def test_code_faux_ou_absent(self):
        self.assertEqual(self.service.verifier(f"{self.numero} 0000000000")["statut"],
                         "falsifie")
        self.assertEqual(self.service.verifier(self.numero)["statut"], "non_controle")

    def test_introuvable_et_illisible(self):
        self.assertEqual(self.service.verifier("REC-2030-999999")["statut"], "introuvable")
        self.assertEqual(self.service.verifier("blabla")["statut"], "invalide")

    def test_recu_annule(self):
        eleves, paiements = EleveRepository(self.conn), PaiementRepository(self.conn)
        PaiementService(eleves, paiements).annuler_paiement(
            self.paiement.id, "Montant saisi par erreur")
        resultat = self.service.verifier(self.qr)
        self.assertEqual(resultat["statut"], "annule")
        self.assertTrue(resultat["details"]["annule"])

    def test_une_modification_directe_de_la_base_est_detectee(self):
        self.conn.execute("UPDATE paiement SET montant = 50000 WHERE id = ?",
                          (self.paiement.id,))
        self.conn.commit()
        self.assertEqual(self.service.verifier(self.qr)["statut"], "falsifie")

    def test_le_solde_peut_changer_sans_invalider_le_recu(self):
        self.conn.execute("UPDATE paiement SET solde_apres = 12345 WHERE id = ?",
                          (self.paiement.id,))
        self.conn.commit()
        self.assertEqual(self.service.verifier(self.qr)["statut"], "authentique")

    def test_le_pdf_du_recu_avec_qr(self):
        pdf = FPDF()
        pdf.add_page()
        self.assertTrue(dessiner_qr(pdf, self.qr, 10, 10, 24))
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_recu_pdf(
                Eleve(self.eleve, "A", "Un", "6e A", "2026-2027", 100000),
                self.paiement, tmp, ParametresEcole())
            self.assertEqual(chemin.read_bytes()[:4], b"%PDF")
        verification.definir_cle(None)  # sans clé : pas de QR, mais le PDF se génère
        self.assertIsNone(verification.contenu_qr(self.paiement))
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_recu_pdf(
                Eleve(self.eleve, "A", "Un", "6e A", "2026-2027", 100000),
                self.paiement, tmp, ParametresEcole())
            self.assertEqual(chemin.read_bytes()[:4], b"%PDF")


if __name__ == "__main__":
    unittest.main()