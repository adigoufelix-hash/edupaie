import unittest
from pathlib import Path

from edupaie.version import VERSION


class TestInstallation(unittest.TestCase):
    def test_numero_de_version(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")

    def test_le_build_embarque_le_schema_sans_donnees_ni_outils(self):
        spec = Path("EduPaie.spec").read_text(encoding="utf-8")
        self.assertIn("data/schema.sql", spec)
        self.assertIn("COLLECT(", spec)  # mode dossier
        self.assertIn("'outils'", spec)  # les outils du fournisseur sont exclus
        for interdit in ("edupaie.db", "cle_privee", "registre_licences"):
            self.assertNotIn(interdit, spec)

    def test_l_installateur_ne_supprime_jamais_les_donnees(self):
        iss = Path("installateur.iss").read_text(encoding="utf-8-sig")
        self.assertIn("AppId={{", iss)
        self.assertIn("dist\\EduPaie", iss)
        for interdit in ("[UninstallDelete]", "[InstallDelete]", "DelTree", "localappdata"):
            self.assertNotIn(interdit, iss)


if __name__ == "__main__":
    unittest.main()