import tempfile
import unittest
from pathlib import Path

from edupaie.models.entities import Eleve, Paiement
from edupaie.services.recu_pdf import generer_recu_pdf


class TestRecuPdf(unittest.TestCase):
    def test_generation_du_pdf(self):
        eleve = Eleve(1, "Dossou", "Marie", "3e A", "2026-2027", 180000)
        paiement = Paiement(5, 1, "REC-2026-000005", 60000,
                            "2026-09-09", "mobile_money", 120000)
        with tempfile.TemporaryDirectory() as dossier:
            chemin = generer_recu_pdf(eleve, paiement, dossier)
            self.assertEqual(chemin.name, "REC-2026-000005.pdf")
            contenu = Path(chemin).read_bytes()
            self.assertTrue(contenu.startswith(b"%PDF"))
            self.assertGreater(len(contenu), 500)


if __name__ == "__main__":
    unittest.main()