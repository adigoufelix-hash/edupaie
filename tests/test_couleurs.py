import colorsys
import re
import sqlite3
import tempfile
import unittest

from edupaie.repositories.ecole_repository import EcoleRepository
from edupaie.services import couleurs
from edupaie.services.cloture_pdf import generer_cloture_pdf
from edupaie.services.ecole import ParametresEcole, courant, definir
from edupaie.services.ecole_service import EcoleService
from edupaie.services.impayes_pdf import generer_impayes_pdf
from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.recu_pdf import generer_recu_pdf
from tests.test_ecole import CLOTURE, ELEVE, IMPAYES, PAIEMENT


def teinte(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))[0] * 360


class TestCouleurs(unittest.TestCase):
    def test_normaliser(self):
        self.assertEqual(couleurs.normaliser("#4f46e5"), "#4F46E5")
        self.assertEqual(couleurs.normaliser("4f46e5"), "#4F46E5")
        for faux in ("#FFF", "rouge", "", None, "#GGGGGG"):
            self.assertIsNone(couleurs.normaliser(faux))

    def test_contraste(self):
        self.assertAlmostEqual(couleurs.contraste((0, 0, 0), (255, 255, 255)), 21, places=1)

    def test_une_couleur_trop_claire_est_assombrie(self):
        self.assertEqual(couleurs.ajuster_principale("#4F46E5"), ("#4F46E5", False))
        code, modifiee = couleurs.ajuster_principale("#FFD400")
        self.assertTrue(modifiee)
        self.assertGreaterEqual(
            couleurs.contraste(couleurs.principale_rgb("#FFD400"), couleurs.BLANC), 4.5)
        self.assertEqual(couleurs.ajuster_principale("rouge"), (None, False))
        self.assertEqual(couleurs.principale_rgb(""), couleurs.BASE_PRINCIPALE)

    def test_la_couleur_choisie_devient_la_couleur_principale(self):
        for cible in ("#0F766E", "#9F1239", "#1D4ED8", "#334155"):
            obtenu = couleurs.theme_rgb(cible, couleurs.BASE_PRINCIPALE)
            attendu = couleurs.principale_rgb(cible)
            self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(obtenu, attendu)), cible)

    def test_seules_les_couleurs_de_la_marque_changent(self):
        for neutre in ((107, 114, 128), (220, 38, 38), (22, 101, 52), (255, 255, 255)):
            self.assertEqual(couleurs.theme_rgb("#0F766E", neutre), neutre)

    def test_la_teinte_et_la_clarte_suivent_la_couleur(self):
        cible = "#9F1239"
        sombre = couleurs.sombre_rgb(cible)
        ecart = abs(teinte(sombre) - teinte(couleurs.principale_rgb(cible)))
        self.assertLess(min(ecart, 360 - ecart), 5)
        self.assertLess(sum(sombre) / 3, 90)  # le menu reste sombre

    def test_feuille_de_style(self):
        style = ("QPushButton { background: #4f46e5; color: #ffffff; } "
                 "QPushButton#danger { background: #dc2626; } "
                 "#cote { background: rgb(30, 27, 75); } "
                 "QLabel { color: rgba(79, 70, 229, 0.5); }")
        nouveau = couleurs.appliquer_a_style(style, "#0F766E")
        self.assertIn("#dc2626", nouveau)         # rouge « supprimer » inchangé
        self.assertIn("#ffffff", nouveau)
        self.assertIn("QPushButton#danger", nouveau)
        self.assertNotIn("rgb(30, 27, 75)", nouveau)
        self.assertNotIn("#4f46e5", nouveau)
        self.assertIn("rgba(", nouveau)
        self.assertIn(", 0.5)", nouveau)          # la transparence est conservée
        principale = couleurs.appliquer_a_style("#4f46e5", "#0F766E")
        self.assertTrue(re.fullmatch(r"#[0-9a-f]{6}", principale))
        self.assertTrue(all(abs(int(principale[i:i + 2], 16) - c) <= 2
                            for i, c in zip((1, 3, 5), (15, 118, 110))))

    def test_couleur_absente_ou_d_origine_ne_change_rien(self):
        style = "QPushButton { background: #4f46e5; }"
        for couleur in ("", None, "#4F46E5", "rouge"):
            self.assertEqual(couleurs.appliquer_a_style(style, couleur), style)


class TestCouleurEcole(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.service = EcoleService(EcoleRepository(self.conn))

    def tearDown(self):
        definir(ParametresEcole())
        self.conn.close()

    def test_couleur_enregistree_normalisee_conservee_puis_reinitialisee(self):
        self.service.enregistrer("École", couleur="0f766e")
        self.assertEqual(self.service.lire().couleur, "#0F766E")
        self.assertEqual(courant().couleur, "#0F766E")
        self.service.enregistrer("École 2")  # couleur inchangée
        self.assertEqual(self.service.lire().couleur, "#0F766E")
        self.service.enregistrer("École 2", couleur="")
        self.assertEqual(self.service.lire().couleur, "")

    def test_couleur_invalide_refusee(self):
        for faux in ("rouge", "#12", "#GGGGGG"):
            with self.assertRaises(ErreurMetier):
                self.service.enregistrer("École", couleur=faux)

    def test_couleurs_par_defaut_des_parametres(self):
        p = ParametresEcole()
        self.assertEqual((p.couleur_principale, p.couleur_sombre),
                         (couleurs.BASE_PRINCIPALE, couleurs.MARINE))

    def test_pdf_aux_couleurs_de_l_ecole(self):
        for couleur in ("", "#9F1239", "#FFD400"):
            ecole = ParametresEcole("École test", couleur=couleur)
            with tempfile.TemporaryDirectory() as tmp:
                for chemin in (generer_recu_pdf(ELEVE, PAIEMENT, tmp, ecole),
                               generer_cloture_pdf(CLOTURE, tmp, ecole),
                               generer_impayes_pdf(IMPAYES, tmp, ecole)):
                    self.assertEqual(chemin.read_bytes()[:4], b"%PDF")


if __name__ == "__main__":
    unittest.main()