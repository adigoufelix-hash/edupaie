import sqlite3
import tempfile
import unittest
from io import BytesIO

from PIL import Image

from edupaie.models.entities import Eleve, Paiement
from edupaie.repositories.ecole_repository import EcoleRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.cloture_pdf import generer_cloture_pdf
from edupaie.services.ecole import ParametresEcole, courant, definir
from edupaie.services.ecole_service import EcoleService
from edupaie.services.impayes_pdf import generer_impayes_pdf
from edupaie.services.paiement_service import ErreurMetier
from edupaie.services.recu_pdf import generer_recu_pdf


def petit_logo(taille=(80, 40)):
    tampon = BytesIO()
    Image.new("RGB", taille, (200, 30, 30)).save(tampon, format="PNG")
    return tampon.getvalue()


def base_en_memoire():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open("data/schema.sql", encoding="utf-8") as f:
        conn.executescript(f.read())
    return conn


class TestEcoleService(unittest.TestCase):
    def setUp(self):
        self.conn = base_en_memoire()
        self.service = EcoleService(EcoleRepository(self.conn))

    def tearDown(self):
        definir(ParametresEcole())

    def test_valeurs_par_defaut(self):
        p = self.service.lire()
        self.assertEqual((p.nom, p.logo, p.coordonnees), ("", None, ""))
        self.assertEqual(p.nom_affiche, "EduPaie")

    def test_enregistrer_relire_et_mettre_a_jour_les_pdf(self):
        self.service.enregistrer("  Collège   Saint-Joseph ", "Rue des Écoles",
                                 "+228 90 12 34 56", "contact@ecole.tg")
        p = self.service.lire()
        self.assertEqual(p.nom, "Collège Saint-Joseph")
        self.assertEqual(p.coordonnees,
                         "Rue des Écoles - +228 90 12 34 56 - contact@ecole.tg")
        self.assertEqual(courant().nom, "Collège Saint-Joseph")
        self.service.enregistrer("Autre nom")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ecole").fetchone()[0], 1)

    def test_le_logo_est_garde_remplace_ou_retire(self):
        logo = petit_logo()
        self.service.enregistrer("École", logo=logo)
        self.assertEqual(self.service.lire().logo, logo)
        self.service.enregistrer("École 2")  # logo inchangé
        self.assertEqual(self.service.lire().logo, logo)
        self.service.enregistrer("École 2", logo=None)
        self.assertIsNone(self.service.lire().logo)

    def test_donnees_invalides_refusees(self):
        for kwargs in ({"nom": ""}, {"nom": "   "}, {"nom": "x" * 81},
                       {"nom": "École", "email": "pas-un-email"},
                       {"nom": "École", "telephone": "9" * 41},
                       {"nom": "École", "logo": b"GIF89a pas un png"},
                       {"nom": "École", "logo": b"\x89PNG\r\n\x1a\n" + b"0" * 1_000_001}):
            with self.assertRaises(ErreurMetier):
                self.service.enregistrer(**kwargs)
        self.assertEqual(self.service.lire().nom, "")

    def test_seul_un_admin_modifie_les_parametres(self):
        utilisateurs = UtilisateurRepository(self.conn)
        auth = AuthService(utilisateurs)
        service = EcoleService(EcoleRepository(self.conn), auth)
        for nom, role in (("caisse", "comptable"), ("admin", "admin")):
            identifiant = utilisateurs.creer(nom, nom, "x", role)
            auth.utilisateur = {"id": identifiant, "login": nom,
                                "nom_complet": nom, "role": role}
            if role == "comptable":
                with self.assertRaises(ErreurMetier):
                    service.enregistrer("École")
            else:
                service.enregistrer("École")
                self.assertEqual(service.lire().nom, "École")


ELEVE = Eleve(None, "Kouassi", "Kofi", "6e A", "2026-2027", 100000)
PAIEMENT = Paiement(id=1, eleve_id=1, numero_recu="REC-2026-000001", montant=40000,
                    date_paiement="2026-10-26", mode="especes", solde_apres=60000,
                    encaisse_par="Caissier")
LIGNE_PAIEMENT = {"numero_recu": "REC-2026-000001", "date_paiement": "2026-09-01",
                  "nom": "Kouassi", "prenom": "Kofi", "classe": "6e A",
                  "mode": "especes", "montant": 40000}
PAR_MODE = {"especes": 40000, "cheque": 0, "virement": 0, "mobile_money": 0}
CLOTURE = {"debut": "2026-09-01", "fin": "2026-09-30", "portee": "Tous les caissiers",
           "genere_par": "Administrateur", "total": 40000, "nb": 1, "par_mode": PAR_MODE,
           "caissiers": [{"nom": "Caissier", "nb": 1, "total": 40000,
                          "par_mode": PAR_MODE, "paiements": [LIGNE_PAIEMENT]}],
           "annules": {"nb": 0, "total": 0, "paiements": []}}
IMPAYES = {"date_ref": "2026-10-25", "total_retard": 40000, "sans_echeancier": 1,
           "lignes": [{"nom": "Kouassi Kofi", "classe": "6e A", "tranche": "1re tranche",
                       "date_limite": "2026-10-15", "jours": 10, "exigible": 40000,
                       "paye": 0, "retard": 40000, "telephone": "+228 90 12 34 56"}]}


class TestPdfAvecEcole(unittest.TestCase):
    ECOLES = [
        ParametresEcole(),
        ParametresEcole("Collège Saint-Joseph de Lomé - Section Bilingue Internationale",
                        "Rue des Écoles, quartier Adidogomé, Lomé", "+228 90 12 34 56",
                        "contact@ecole.tg", petit_logo()),
        ParametresEcole("Œuvre Đức Nguyễn", logo=petit_logo((30, 90))),
        ParametresEcole("École test", logo=b"pas une image"),
    ]

    def tearDown(self):
        definir(ParametresEcole())

    def _verifier(self, chemin):
        self.assertEqual(chemin.read_bytes()[:4], b"%PDF")

    def test_recu_avec_chaque_variante_d_ecole(self):
        for ecole in self.ECOLES:
            with self.subTest(ecole=ecole.nom), tempfile.TemporaryDirectory() as tmp:
                self._verifier(generer_recu_pdf(ELEVE, PAIEMENT, tmp, ecole))

    def test_cloture_avec_chaque_variante_d_ecole(self):
        for ecole in self.ECOLES:
            with self.subTest(ecole=ecole.nom), tempfile.TemporaryDirectory() as tmp:
                self._verifier(generer_cloture_pdf(CLOTURE, tmp, ecole))

    def test_impayes_avec_chaque_variante_d_ecole(self):
        for ecole in self.ECOLES:
            with self.subTest(ecole=ecole.nom), tempfile.TemporaryDirectory() as tmp:
                self._verifier(generer_impayes_pdf(IMPAYES, tmp, ecole))

    def test_les_pdf_utilisent_les_parametres_courants_par_defaut(self):
        definir(self.ECOLES[1])
        with tempfile.TemporaryDirectory() as tmp:
            self._verifier(generer_recu_pdf(ELEVE, PAIEMENT, tmp))
            self._verifier(generer_cloture_pdf(CLOTURE, tmp))
            self._verifier(generer_impayes_pdf(IMPAYES, tmp))


if __name__ == "__main__":
    unittest.main()