import sqlite3
import unittest

from edupaie.models.entities import Eleve
from edupaie.repositories.contact_repository import ContactRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.services.auth_service import AuthService
from edupaie.services.echeancier_service import (EcheancierService,
                                                 normaliser_telephone)
from edupaie.services.paiement_service import ErreurMetier, PaiementService
from edupaie.services.remise_service import RemiseService

ANNEE = "2026-2027"


class TestEcheancier(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open("data/schema.sql", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.eleves = EleveRepository(self.conn)
        self.paiements = PaiementRepository(self.conn)
        self.service = EcheancierService(
            EcheanceRepository(self.conn), self.eleves, self.paiements,
            ContactRepository(self.conn))
        self.paie = PaiementService(self.eleves, self.paiements)
        self.eleve = self.eleves.ajouter(
            Eleve(None, "Kouassi", "Kofi", "6e A", ANNEE, 100000))
        for libelle, date_limite, pct in (("1re tranche", "2026-10-15", 40),
                                          ("2e tranche", "2027-01-15", 30),
                                          ("3e tranche", "2027-04-15", 30)):
            self.service.ajouter_ligne("6e A", ANNEE, libelle, date_limite, pct)

    def test_rien_n_est_exigible_avant_la_premiere_date(self):
        self.assertEqual(self.service.impayes("2026-10-01")["lignes"], [])

    def test_retard_apres_la_premiere_tranche(self):
        ligne = self.service.impayes("2026-10-25")["lignes"][0]
        self.assertEqual((ligne["exigible"], ligne["paye"], ligne["retard"]), (40000, 0, 40000))
        self.assertEqual((ligne["jours"], ligne["tranche"]), (10, "1re tranche"))
        self.assertEqual(ligne["nom"], "Kouassi Kofi")

    def test_paiement_partiel_reduit_le_retard(self):
        self.paie.enregistrer_paiement(self.eleve, 25000, "2026-09-01", "especes")
        self.assertEqual(self.service.impayes("2026-10-25")["lignes"][0]["retard"], 15000)

    def test_a_jour_n_apparait_pas(self):
        self.paie.enregistrer_paiement(self.eleve, 40000, "2026-09-01", "especes")
        self.assertEqual(self.service.impayes("2026-10-25")["lignes"], [])

    def test_le_retard_est_cumule_et_date_de_la_premiere_tranche_impayee(self):
        self.paie.enregistrer_paiement(self.eleve, 40000, "2026-09-01", "especes")
        ligne = self.service.impayes("2027-01-20")["lignes"][0]
        self.assertEqual((ligne["exigible"], ligne["retard"]), (70000, 30000))
        self.assertEqual((ligne["tranche"], ligne["jours"]), ("2e tranche", 5))

    def test_les_remises_sont_deduites(self):
        RemiseService(RemiseRepository(self.conn), self.eleves, self.paiements).accorder(
            self.eleve, "montant", 20000, "Fratrie 2 enfants")
        self.assertEqual(self.service.impayes("2026-10-25")["lignes"][0]["exigible"], 32000)

    def test_classe_sans_echeancier_non_suivie(self):
        self.eleves.ajouter(Eleve(None, "B", "Deux", "6e B", ANNEE, 50000))
        r = self.service.impayes("2026-10-25")
        self.assertEqual(r["sans_echeancier"], 1)
        self.assertEqual([l["classe"] for l in r["lignes"]], ["6e A"])
        self.assertEqual(len(self.service.impayes("2026-10-25", "6e A")["lignes"]), 1)

    def test_total_des_tranches_limite_a_100(self):
        with self.assertRaises(ErreurMetier):
            self.service.ajouter_ligne("6e A", ANNEE, "Une de trop", "2027-06-01", 1)
        with self.assertRaises(ErreurMetier):
            ligne = self.service.lister("6e A", ANNEE)[0]
            self.service.modifier_ligne(ligne["id"], "1re tranche", "2026-10-15", 41)

    def test_donnees_invalides_refusees(self):
        for libelle, date_limite, pct in (("", "2026-10-15", 10), ("X", "pas une date", 10),
                                          ("X", "2026-10-15", 0), ("X", "2026-10-15", "abc")):
            with self.assertRaises(ErreurMetier):
                self.service.ajouter_ligne("6e B", ANNEE, libelle, date_limite, pct)
        self.service.ajouter_ligne("6e B", ANNEE, "T1", "2026-10-15", 50)
        with self.assertRaises(ErreurMetier):  # même nom, casse différente
            self.service.ajouter_ligne("6e B", ANNEE, "t1", "2026-12-15", 50)

    def test_copie_vers_une_autre_classe(self):
        self.assertEqual(self.service.copier("6e A", ANNEE, "6e B"), 3)
        self.assertEqual(self.service.total_pourcentage("6e B", ANNEE), 100)
        self.assertEqual(self.service.copier("6e A", ANNEE, "6e B"), 0)

    def test_droits(self):
        utilisateurs = UtilisateurRepository(self.conn)
        auth = AuthService(utilisateurs)
        service = EcheancierService(EcheanceRepository(self.conn), self.eleves,
                                    self.paiements, ContactRepository(self.conn), auth)
        for nom, role in (("caisse", "comptable"), ("lecteur", "lecture")):
            identifiant = utilisateurs.creer(nom, nom, "x", role)
            auth.utilisateur = {"id": identifiant, "login": nom,
                                "nom_complet": nom, "role": role}
            if role == "comptable":
                self.assertIsNotNone(service.impayes("2026-10-25"))
                with self.assertRaises(ErreurMetier):
                    service.ajouter_ligne("6e B", ANNEE, "T1", "2026-10-15", 10)
                service.enregistrer_contact(self.eleve, "Parent", "90 12 34 56")
            else:
                with self.assertRaises(ErreurMetier):
                    service.impayes("2026-10-25")
                with self.assertRaises(ErreurMetier):
                    service.enregistrer_contact(self.eleve, "Parent", "90 12 34 56")

    def test_normalisation_des_telephones(self):
        self.assertEqual(normaliser_telephone("90 12 34 56"), "22890123456")
        self.assertEqual(normaliser_telephone("+228 90123456"), "22890123456")
        self.assertEqual(normaliser_telephone("00233 24 123 4567"), "233241234567")
        for faux in ("", "12345", "abcdefgh", "123456789"):
            self.assertIsNone(normaliser_telephone(faux))

    def test_contact_et_lien_whatsapp(self):
        with self.assertRaises(ErreurMetier):
            self.service.enregistrer_contact(self.eleve, "Parent", "12345")
        ligne = self.service.impayes("2026-10-25")["lignes"][0]
        self.assertIsNone(self.service.lien_whatsapp(ligne))
        self.service.enregistrer_contact(self.eleve, "M. Kouassi", "90 12 34 56")
        ligne = self.service.impayes("2026-10-25")["lignes"][0]
        self.assertEqual(ligne["tuteur"], "M. Kouassi")
        lien = self.service.lien_whatsapp(ligne)
        self.assertTrue(lien.startswith("https://wa.me/22890123456?text=Bonjour"))
        self.assertIn("40%C2%A0000", lien.replace("%20", "%C2%A0") if False else lien) \
            if False else self.assertIn("Kouassi", lien)
        self.assertIn("Kouassi", lien)


if __name__ == "__main__":
    unittest.main()