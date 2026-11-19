from PySide6.QtCore import QPoint, QPropertyAnimation, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout)

from edupaie.services.ecole import courant
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.icones import icone_cadenas, icone_utilisateur
from edupaie.ui.oeil import ajouter_oeil
from edupaie.ui.recuperation_dialogs import (ChangementObligatoireDialog,
                                             CodesSecoursDialog, RecuperationDialog)
from edupaie.version import VERSION

STYLE = """
QDialog#connexion { background: #ffffff; }
QFrame#gauche {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @SOMBRE@, stop:1 @PRINCIPALE@);
}
QFrame#droite { background: #ffffff; }
QLabel { background: transparent; }
QLabel#badge { background: rgba(255, 255, 255, 46); border-radius: 22px; color: #ffffff;
               font-size: 30px; font-weight: 800; }
QLabel#marqueNom { color: #ffffff; font-size: 26px; font-weight: 800; }
QLabel#marqueAccroche { color: rgba(255, 255, 255, 204); font-size: 14px; }
QLabel#marquePoint { color: rgba(255, 255, 255, 235); font-size: 13px; }
QLabel#marqueVersion { color: rgba(255, 255, 255, 140); font-size: 11px; }
QLabel#titre { color: #111827; font-size: 28px; font-weight: 800; }
QLabel#sousTitre { color: #6b7280; font-size: 14px; }
QLabel#etiquette { color: #374151; font-size: 12px; font-weight: 700; }
QLabel#aide { color: #6b7280; font-size: 12px; }
QLabel#pied { color: #9ca3af; font-size: 11px; }
QLabel#erreur { color: #991b1b; background: #fee2e2; border-radius: 10px; padding: 10px 12px;
                font-size: 13px; }
QFrame#droite QLineEdit { background: #f9fafb; border: 1.5px solid #e5e7eb; border-radius: 10px;
                          padding: 10px 8px; font-size: 14px; color: #111827;
                          selection-background-color: @PRINCIPALE@; }
QFrame#droite QLineEdit:focus { background: #ffffff; border: 1.5px solid @PRINCIPALE@; }
QPushButton#principal { background: @PRINCIPALE@; color: #ffffff; border: none;
                        border-radius: 10px; padding: 12px; font-size: 15px; font-weight: 700; }
QPushButton#principal:hover { background: @SOMBRE@; }
QPushButton#principal:pressed { background: @SOMBRE@; padding-top: 14px; }
"""


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


class LoginDialog(QDialog):
    MAX_ESSAIS = 5

    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.premier_lancement = auth.aucun_utilisateur()
        self.essais = 0
        ecole = courant()
        principale, sombre = _hex(ecole.couleur_principale), _hex(ecole.couleur_sombre)

        self.setObjectName("connexion")
        self.setModal(True)
        self.setMinimumSize(800, 580)
        self.resize(880, 620)
        self.setStyleSheet(STYLE.replace("@PRINCIPALE@", principale).replace("@SOMBRE@", sombre))
        self.setWindowTitle(
            "EduPaie : création du compte administrateur"
            if self.premier_lancement else "EduPaie : connexion")

        # --- Panneau de marque (à gauche)
        gauche = QFrame()
        gauche.setObjectName("gauche")
        gauche.setFixedWidth(340)
        marque = QVBoxLayout(gauche)
        marque.setContentsMargins(36, 48, 36, 30)
        marque.setSpacing(0)
        marque.addWidget(self._badge(ecole), 0, Qt.AlignmentFlag.AlignLeft)
        marque.addSpacing(22)
        nom_ecole = QLabel(ecole.nom_affiche)
        nom_ecole.setObjectName("marqueNom")
        nom_ecole.setWordWrap(True)
        marque.addWidget(nom_ecole)
        marque.addSpacing(6)
        accroche = QLabel("Gestion des paiements scolaires")
        accroche.setObjectName("marqueAccroche")
        accroche.setWordWrap(True)
        marque.addWidget(accroche)
        marque.addSpacing(34)
        for texte in ("Reçus PDF vérifiables par QR code", "Suivi des impayés et relances",
                      "Sauvegardes automatiques", "Journal de toutes les opérations"):
            point = QLabel("✓   " + texte)
            point.setObjectName("marquePoint")
            marque.addWidget(point)
            marque.addSpacing(10)
        marque.addStretch(1)
        version = QLabel(f"EduPaie {VERSION}")
        version.setObjectName("marqueVersion")
        marque.addWidget(version)

        # --- Formulaire (à droite)
        droite = QFrame()
        droite.setObjectName("droite")
        colonne = QVBoxLayout(droite)
        colonne.setContentsMargins(60, 36, 60, 28)
        colonne.setSpacing(0)
        colonne.addStretch(1)
        titre = QLabel("Créer le compte administrateur" if self.premier_lancement
                       else "Bienvenue")
        titre.setObjectName("titre")
        titre.setWordWrap(True)
        sous_titre = QLabel(
            "Premier lancement : ce compte gérera l'école, ses utilisateurs et ses sauvegardes."
            if self.premier_lancement else "Connectez-vous pour accéder à la caisse.")
        sous_titre.setObjectName("sousTitre")
        sous_titre.setWordWrap(True)
        colonne.addWidget(titre)
        colonne.addSpacing(6)
        colonne.addWidget(sous_titre)
        colonne.addSpacing(26)

        self.nom = self.mdp2 = None
        if self.premier_lancement:
            self.nom = self._champ("Nom complet", icone_utilisateur())
            self._ajouter_champ(colonne, "NOM COMPLET", self.nom)
        self.login = self._champ("Identifiant", icone_utilisateur())
        self._ajouter_champ(colonne, "IDENTIFIANT", self.login)
        self.mdp = self._champ("Mot de passe", icone_cadenas(), mot_de_passe=True)
        self._ajouter_champ(colonne, "MOT DE PASSE", self.mdp)
        if self.premier_lancement:
            self.mdp2 = self._champ("Confirmez le mot de passe", icone_cadenas(),
                                    mot_de_passe=True)
            self._ajouter_champ(colonne, "CONFIRMATION", self.mdp2)
            aide = QLabel("8 caractères minimum, avec au moins une lettre et un chiffre. "
                          "Notez-le bien : des codes de secours vous seront remis ensuite.")
            aide.setObjectName("aide")
            aide.setWordWrap(True)
            colonne.addWidget(aide)
            colonne.addSpacing(10)

        self.erreur = QLabel("")
        self.erreur.setObjectName("erreur")
        self.erreur.setWordWrap(True)
        self.erreur.hide()
        colonne.addWidget(self.erreur)
        colonne.addSpacing(12)

        self.bouton = QPushButton("Créer le compte" if self.premier_lancement
                                  else "Se connecter")
        self.bouton.setObjectName("principal")
        self.bouton.setMinimumHeight(48)
        self.bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton.setDefault(True)
        self.bouton.clicked.connect(self._valider)
        colonne.addWidget(self.bouton)

        self.oublie = QLabel(
            f"<a href='#' style='color:{principale}; text-decoration:none;'>"
            "Mot de passe oublié ?</a>")
        self.oublie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.oublie.linkActivated.connect(self._oublie)
        self.oublie.setVisible(not self.premier_lancement)
        colonne.addSpacing(16)
        colonne.addWidget(self.oublie)
        colonne.addStretch(1)
        if not self.premier_lancement:
            pied = QLabel("Votre session se verrouille après 5 minutes d'inactivité.")
            pied.setObjectName("pied")
            pied.setAlignment(Qt.AlignmentFlag.AlignCenter)
            colonne.addWidget(pied)

        disposition = QHBoxLayout(self)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(0)
        disposition.addWidget(gauche)
        disposition.addWidget(droite, 1)
        (self.nom or self.login).setFocus()

    # --- Construction -------------------------------------------------------------------------
    @staticmethod
    def _badge(ecole) -> QLabel:
        badge = QLabel()
        badge.setObjectName("badge")
        badge.setFixedSize(88, 88)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = QPixmap()
        if ecole.logo and logo.loadFromData(ecole.logo):
            badge.setStyleSheet("background: #ffffff; border-radius: 22px;")
            badge.setPixmap(logo.scaled(68, 68, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
        else:
            mots = ecole.nom.split()[:2] if ecole.nom else []
            badge.setText("".join(m[0] for m in mots).upper() or "EP")
        return badge

    @staticmethod
    def _champ(indication, icone, mot_de_passe=False) -> QLineEdit:
        champ = QLineEdit()
        champ.setPlaceholderText(indication)
        champ.addAction(icone, QLineEdit.ActionPosition.LeadingPosition)
        if mot_de_passe:
            champ.setEchoMode(QLineEdit.EchoMode.Password)
            ajouter_oeil(champ)  # l'œil pour afficher ou masquer ce qu'on tape
        return champ

    @staticmethod
    def _ajouter_champ(colonne, etiquette, champ):
        texte = QLabel(etiquette)
        texte.setObjectName("etiquette")
        colonne.addWidget(texte)
        colonne.addSpacing(6)
        colonne.addWidget(champ)
        colonne.addSpacing(14)

    # --- Animations ------------------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_deja_affiche", False):  # fondu à l'ouverture
            self._deja_affiche = True
            self.setWindowOpacity(0.0)
            self._fondu = QPropertyAnimation(self, b"windowOpacity", self)
            self._fondu.setDuration(350)
            self._fondu.setStartValue(0.0)
            self._fondu.setEndValue(1.0)
            self._fondu.start()

    def _secouer(self):
        """Petite secousse quand les identifiants sont refusés."""
        depart = self.pos()
        self._secousse = QPropertyAnimation(self, b"pos", self)
        self._secousse.setDuration(350)
        for instant, decalage in ((0, 0), (0.15, -10), (0.35, 10), (0.55, -8),
                                  (0.75, 6), (1, 0)):
            self._secousse.setKeyValueAt(instant, depart + QPoint(decalage, 0))
        self._secousse.start()

    def _erreur(self, texte: str, secouer: bool = False):
        self.erreur.setText(texte)
        self.erreur.setVisible(bool(texte))
        if texte and secouer:
            self._secouer()

    # --- Logique (inchangée) -----------------------------------------------------------------------
    def _valider(self):
        self._erreur("")
        if self.premier_lancement:
            self._creer_admin()
        else:
            self._connecter()

    def _nouveau_mot_de_passe(self) -> bool:
        return ChangementObligatoireDialog(self.auth, self).exec() == QDialog.Accepted

    def _connecter(self):
        try:
            utilisateur = self.auth.authentifier(self.login.text(), self.mdp.text())
        except ErreurMetier as e:  # trop de tentatives
            self._erreur(str(e), secouer=True)
            return
        if utilisateur:
            if utilisateur.get("doit_changer_mdp") and not self._nouveau_mot_de_passe():
                self.auth.deconnecter()
                self.mdp.clear()
                self._erreur("Tu dois choisir un nouveau mot de passe pour te connecter.")
                return
            self.accept()
            return
        self.essais += 1
        if self.essais >= self.MAX_ESSAIS:
            self.reject()
            return
        restants = self.MAX_ESSAIS - self.essais
        self._erreur(f"Identifiants incorrects. Il vous reste {restants} essai(s).",
                     secouer=True)
        self.mdp.clear()
        self.mdp.setFocus()

    def _creer_admin(self):
        if not self.nom.text().strip() or not self.login.text().strip():
            self._erreur("Le nom complet et l'identifiant sont obligatoires.")
            return
        if self.mdp.text() != self.mdp2.text():
            self._erreur("Les deux mots de passe ne correspondent pas.", secouer=True)
            return
        try:
            self.auth.creer_utilisateur(
                self.login.text(), self.nom.text(), self.mdp.text(), "admin")
        except (ErreurMetier, ValueError) as e:
            self._erreur(str(e))
            return
        self.auth.authentifier(self.login.text(), self.mdp.text())
        try:
            codes = self.auth.generer_codes_secours(self.mdp.text())
        except ErreurMetier:
            codes = []
        if codes:  # à noter tout de suite : ils ne seront plus affichés
            CodesSecoursDialog(codes, self.nom.text().strip(), self).exec()
        self.accept()

    def _oublie(self, *_):
        dialogue = RecuperationDialog(self.auth, self.login.text(), self)
        if dialogue.exec() == QDialog.Accepted:
            self.login.setText(dialogue.login_saisi)
            self.mdp.clear()
            self.mdp.setFocus()
            self._erreur("")
            self.essais = 0
