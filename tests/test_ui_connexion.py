import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # pas de fenêtre réelle pendant les tests

from PySide6.QtWidgets import QApplication, QDialog, QLineEdit  # noqa: E402

from edupaie.ui.login_dialog import LoginDialog  # noqa: E402
from edupaie.ui.oeil import ajouter_oeil, installer_oeil  # noqa: E402

app = QApplication.instance() or QApplication([])


class FausseAuth:
    def __init__(self, premier=False):
        self.premier = premier
        self.crees = []

    def aucun_utilisateur(self):
        return self.premier

    def authentifier(self, login, mdp):
        if (login, mdp) == ("admin", "Secret123"):
            return {"nom_complet": "Administrateur", "role": "admin"}
        return None

    def deconnecter(self):
        pass

    def creer_utilisateur(self, login, nom, mdp, role):
        self.crees.append((login, nom, role))

    def generer_codes_secours(self, mdp):
        return []  # pas de fenêtre de codes pendant le test


def oeil(champ):
    return next(a for a in champ.actions() if "mot de passe" in a.toolTip())


class TestOeil(unittest.TestCase):
    def test_afficher_et_masquer(self):
        champ = QLineEdit()
        champ.setEchoMode(QLineEdit.EchoMode.Password)
        ajouter_oeil(champ)
        ajouter_oeil(champ)  # sans effet la deuxième fois
        self.assertEqual(len(champ.actions()), 1)
        action = oeil(champ)
        self.assertIn("Afficher", action.toolTip())
        action.trigger()
        self.assertEqual(champ.echoMode(), QLineEdit.EchoMode.Normal)
        self.assertIn("Masquer", action.toolTip())
        action.trigger()
        self.assertEqual(champ.echoMode(), QLineEdit.EchoMode.Password)

    def test_installation_pour_toute_l_application(self):
        self.assertTrue(installer_oeil())
        secret, libre = QLineEdit(), QLineEdit()
        secret.setEchoMode(QLineEdit.EchoMode.Password)
        libre.setEchoMode(QLineEdit.EchoMode.Normal)
        self.assertEqual(len(secret.actions()), 1)
        self.assertEqual(len(libre.actions()), 0)


class TestConnexion(unittest.TestCase):
    def test_connexion_reussie(self):
        d = LoginDialog(FausseAuth())
        self.assertTrue(d.erreur.isHidden())
        d.login.setText("admin")
        d.mdp.setText("Secret123")
        d.bouton.click()
        self.assertEqual(d.result(), QDialog.Accepted)

    def test_identifiants_incorrects(self):
        d = LoginDialog(FausseAuth())
        d.login.setText("admin")
        for restant in (4, 3, 2, 1):
            d.mdp.setText("faux")
            d.bouton.click()
            self.assertFalse(d.erreur.isHidden())
            self.assertIn(f"{restant} essai", d.erreur.text())
            self.assertEqual(d.mdp.text(), "")
        d.mdp.setText("faux")
        d.bouton.click()  # cinquième échec : la fenêtre se ferme
        self.assertEqual(d.result(), QDialog.Rejected)

    def test_l_oeil_du_mot_de_passe(self):
        d = LoginDialog(FausseAuth())
        d.mdp.setText("Secret123")
        self.assertEqual(d.mdp.echoMode(), QLineEdit.EchoMode.Password)
        oeil(d.mdp).trigger()
        self.assertEqual(d.mdp.echoMode(), QLineEdit.EchoMode.Normal)
        self.assertEqual(d.mdp.text(), "Secret123")  # le texte saisi est conservé
        oeil(d.mdp).trigger()
        self.assertEqual(d.mdp.echoMode(), QLineEdit.EchoMode.Password)

    def test_premier_lancement(self):
        auth = FausseAuth(premier=True)
        d = LoginDialog(auth)
        self.assertIsNotNone(d.nom)
        self.assertIsNotNone(oeil(d.mdp))
        self.assertIsNotNone(oeil(d.mdp2))  # un œil sur chaque champ de mot de passe
        d.nom.setText("Directeur")
        d.login.setText("directeur")
        d.mdp.setText("Secret123")
        d.mdp2.setText("autre")
        d.bouton.click()
        self.assertFalse(d.erreur.isHidden())
        self.assertIn("ne correspondent pas", d.erreur.text())
        self.assertEqual(auth.crees, [])
        d.mdp2.setText("Secret123")
        d.bouton.click()
        self.assertEqual(auth.crees, [("directeur", "Directeur", "admin")])
        self.assertEqual(d.result(), QDialog.Accepted)


if __name__ == "__main__":
    unittest.main()
