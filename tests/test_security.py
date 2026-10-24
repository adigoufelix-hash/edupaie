import unittest

from edupaie.security import (doit_etre_rehache, hasher_pour_stockage,
                              verifier_complexite, verifier_stocke)


class TestSecurity(unittest.TestCase):
    def test_deux_hash_du_meme_mot_de_passe_sont_differents(self):
        self.assertNotEqual(hasher_pour_stockage("Ecole2026"),
                            hasher_pour_stockage("Ecole2026"))

    def test_bon_mot_de_passe_accepte(self):
        self.assertTrue(verifier_stocke("Ecole2026", hasher_pour_stockage("Ecole2026")))

    def test_mauvais_mot_de_passe_refuse(self):
        self.assertFalse(verifier_stocke("Ecole2027", hasher_pour_stockage("Ecole2026")))

    def test_valeur_stockee_invalide_refusee_sans_planter(self):
        self.assertFalse(verifier_stocke("Ecole2026", "n'importe quoi"))
        self.assertFalse(verifier_stocke("Ecole2026", ""))

    def test_regles_de_complexite(self):
        self.assertEqual(verifier_complexite("Ecole2026"), [])
        self.assertTrue(verifier_complexite("Abc1"))        # trop court
        self.assertTrue(verifier_complexite("abcdefgh"))    # pas de chiffre
        self.assertTrue(verifier_complexite("12345678"))    # pas de lettre

    def test_rehachage_necessaire_pour_un_ancien_hash(self):
        self.assertTrue(doit_etre_rehache("1000$aa$bb"))
        self.assertFalse(doit_etre_rehache(hasher_pour_stockage("Ecole2026")))


if __name__ == "__main__":
    unittest.main()