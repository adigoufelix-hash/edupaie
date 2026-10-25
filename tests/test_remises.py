import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.paiement_service import (STATUT_SOLDE, ErreurMetier,
                                               PaiementService)
from edupaie.services.remise_service import RemiseService


class TestRemises(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            conn.executescript(f.read())
        utilisateurs = UtilisateurRepository(conn)
        self.comptes = {
            "admin": (utilisateurs.creer("admin", "Administrateur", "x", "admin"),
                      "Administrateur", "admin"),
            "caisse": (utilisateurs.creer("caisse", "Caissier", "x", "comptable"),
                       "Caissier", "comptable"),
        }
        self.auth = AuthService(utilisateurs)
        self.eleves = EleveRepository(conn)
        self.paiements = PaiementRepository(conn)
        self.eleve = self.eleves.ajouter(
            Eleve(None, "A", "Un", "6e A", "2026-2027", 100000))
        self.service = PaiementService(self.eleves, self.paiements, self.auth)
        self.remises = RemiseService(
            RemiseRepository(conn), self.eleves, self.paiements, self.auth)
        self.se_connecter("admin")

    def se_connecter(self, nom):
        identifiant, nom_complet, role = self.comptes[nom]
        self.auth.utilisateur = {"id": identifiant, "login": nom,
                                 "nom_complet": nom_complet, "role": role}

    def test_remise_en_montant(self):
        self.remises.accorder(self.eleve, "montant", "20 000", "Fratrie 2 enfants")
        sit = self.service.situation(self.eleve)
        self.assertEqual((sit.total_du, sit.remise, sit.solde), (80000, 20000, 80000))

    def test_remise_en_pourcentage_calculee_sur_les_frais_bruts(self):
        self.remises.accorder(self.eleve, "pourcentage", 25, "Bourse sociale")
        sit = self.service.situation(self.eleve)
        self.assertEqual((sit.remise, sit.solde), (25000, 75000))

    def test_apercu_du_montant(self):
        self.assertEqual(self.remises.montant_effectif(self.eleve, "pourcentage", 10), 10000)
        self.assertEqual(self.remises.montant_effectif(self.eleve, "montant", "5000"), 5000)
        for type_, valeur in (("pourcentage", 101), ("montant", 0), ("montant", "abc")):
            self.assertIsNone(self.remises.montant_effectif(self.eleve, type_, valeur))

    def test_exoneration_totale_solde_l_eleve(self):
        self.remises.accorder(self.eleve, "pourcentage", 100, "Exonération du personnel")
        sit = self.service.situation(self.eleve)
        self.assertEqual((sit.total_du, sit.solde, sit.statut), (0, 0, STATUT_SOLDE))
        with self.assertRaises(ErreurMetier):
            self.service.enregistrer_paiement(self.eleve, 1000, "2026-09-01", "especes")

    def test_la_remise_ne_peut_pas_depasser_le_solde(self):
        self.service.enregistrer_paiement(self.eleve, 90000, "2026-09-01", "especes")
        with self.assertRaises(ErreurMetier):
            self.remises.accorder(self.eleve, "pourcentage", 20, "Fratrie 2 enfants")
        self.remises.accorder(self.eleve, "pourcentage", 10, "Fratrie 2 enfants")
        self.assertEqual(self.service.situation(self.eleve).solde, 0)

    def test_donnees_invalides_refusees(self):
        for type_, valeur, motif in (("montant", 1000, ""), ("montant", 1000, "abc"),
                                     ("montant", 0, "Fratrie"), ("montant", "abc", "Fratrie"),
                                     ("pourcentage", 101, "Fratrie"),
                                     ("autre", 1000, "Fratrie")):
            with self.assertRaises(ErreurMetier):
                self.remises.accorder(self.eleve, type_, valeur, motif)
        self.assertEqual(self.service.situation(self.eleve).remise, 0)

    def test_seul_un_admin_gere_les_remises(self):
        self.se_connecter("caisse")
        self.assertFalse(self.remises.peut_gerer())
        with self.assertRaises(ErreurMetier):
            self.remises.accorder(self.eleve, "montant", 1000, "Fratrie 2 enfants")

    def test_annulation_d_une_remise(self):
        remise_id = self.remises.accorder(self.eleve, "montant", 20000, "Fratrie 2 enfants")
        with self.assertRaises(ErreurMetier):
            self.remises.annuler(remise_id, "")
        self.remises.annuler(remise_id, "Remise accordée par erreur")
        self.assertEqual(self.service.situation(self.eleve).total_du, 100000)
        with self.assertRaises(ErreurMetier):
            self.remises.annuler(remise_id, "Encore une fois")
        liste = self.remises.lister(self.eleve)
        self.assertEqual(len(liste), 1)
        self.assertEqual(liste[0]["annule"], 1)
        self.assertEqual(liste[0]["annule_par"], "Administrateur")

    def test_les_soldes_des_anciens_paiements_sont_recalcules(self):
        p = self.service.enregistrer_paiement(self.eleve, 40000, "2026-09-01", "especes")
        self.assertEqual(p.solde_apres, 60000)
        remise_id = self.remises.accorder(self.eleve, "montant", 10000, "Fratrie 2 enfants")
        self.assertEqual(self.paiements.obtenir(p.id).solde_apres, 50000)
        self.remises.annuler(remise_id, "Remise accordée par erreur")
        self.assertEqual(self.paiements.obtenir(p.id).solde_apres, 60000)

    def test_le_recu_affiche_le_total_apres_remise(self):
        p = self.service.enregistrer_paiement(self.eleve, 40000, "2026-09-01", "especes")
        self.remises.accorder(self.eleve, "montant", 10000, "Fratrie 2 enfants")
        eleve, paiement = self.service.recu(p.id)
        self.assertEqual(eleve.total_du, 90000)
        self.assertEqual(paiement.solde_apres, 50000)

    def test_un_paiement_ne_peut_pas_depasser_le_solde_apres_remise(self):
        self.remises.accorder(self.eleve, "montant", 30000, "Bourse sociale")
        with self.assertRaises(ErreurMetier):
            self.service.enregistrer_paiement(self.eleve, 80000, "2026-09-01", "especes")
        self.service.enregistrer_paiement(self.eleve, 70000, "2026-09-01", "especes")
        self.assertEqual(self.service.situation(self.eleve).statut, STATUT_SOLDE)


if __name__ == "__main__":
    unittest.main()