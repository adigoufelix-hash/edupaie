import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.paiement_service import ErreurMetier, PaiementService


class TestJournalEncaissements(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        self.eleves = EleveRepository(conn)
        self.paiements = PaiementRepository(conn)
        self.auth = AuthService(UtilisateurRepository(conn))
        self.auth.creer_utilisateur("admin", "Administrateur", "Ecole2026", "admin")
        self.auth.authentifier("admin", "Ecole2026")
        self.eleve = self.eleves.ajouter(
            Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        self.service = PaiementService(self.eleves, self.paiements, self.auth)

    def test_le_paiement_enregistre_le_caissier(self):
        p = self.service.enregistrer_paiement(self.eleve, 20000, "2026-09-02", "cheque")
        self.assertEqual(p.encaisse_par, "Administrateur")
        self.assertEqual(p.utilisateur_id, self.auth.utilisateur["id"])
        self.assertEqual(self.service.historique(self.eleve)[0].encaisse_par,
                         "Administrateur")

    def test_un_role_lecture_ne_peut_pas_encaisser(self):
        self.auth.creer_utilisateur("lecteur", "Lecteur", "Lecture2026", "lecture")
        self.auth.deconnecter()
        self.auth.authentifier("lecteur", "Lecture2026")
        with self.assertRaises(ErreurMetier):
            self.service.enregistrer_paiement(self.eleve, 20000, "2026-09-02", "cheque")
        self.assertEqual(self.paiements.total_paye(self.eleve), 0)

    def test_sans_authentification_le_nom_reste_vide(self):
        service = PaiementService(self.eleves, self.paiements)
        p = service.enregistrer_paiement(self.eleve, 20000, "2026-09-02", "cheque")
        self.assertIsNone(p.encaisse_par)

    def test_le_nom_est_conserve_apres_suppression_du_compte(self):
        self.auth.creer_utilisateur("caisse", "Caissier Kofi", "Caisse2026", "comptable")
        self.auth.deconnecter()
        self.auth.authentifier("caisse", "Caisse2026")
        self.service.enregistrer_paiement(self.eleve, 20000, "2026-09-02", "cheque")
        self.auth.deconnecter()
        self.auth.authentifier("admin", "Ecole2026")
        compte = next(u for u in self.auth.lister_utilisateurs() if u["login"] == "caisse")
        self.auth.supprimer_utilisateur(compte["id"])
        p = self.service.historique(self.eleve)[0]
        self.assertEqual(p.encaisse_par, "Caissier Kofi")
        self.assertIsNone(p.utilisateur_id)


if __name__ == "__main__":
    unittest.main()