import os
import signal
import sys

from PySide6.QtWidgets import QApplication, QDialog

from edupaie.db.connection import dossier_donnees, get_connection, initialiser_base
from edupaie.repositories.annee_repository import AnneeRepository
from edupaie.repositories.audit_repository import JournalRepository
from edupaie.repositories.classe_repository import ClasseRepository
from edupaie.repositories.code_secours_repository import CodeSecoursRepository
from edupaie.repositories.contact_repository import ContactRepository
from edupaie.repositories.echeance_repository import EcheanceRepository
from edupaie.repositories.ecole_repository import EcoleRepository
from edupaie.repositories.eleve_repository import EleveRepository
from edupaie.repositories.frais_repository import FraisRepository
from edupaie.repositories.import_repository import ImportRepository
from edupaie.repositories.paiement_repository import PaiementRepository
from edupaie.repositories.remise_repository import RemiseRepository
from edupaie.repositories.utilisateur_repository import UtilisateurRepository
from edupaie.repositories.verification_repository import VerificationRepository
from edupaie.services import audit_regles, verification
from edupaie.services.annee_service import AnneeService
from edupaie.services.audit import Audite, JournalService
from edupaie.services.auth_service import AuthService
from edupaie.services.caisse_service import CaisseService
from edupaie.services.classe_service import ClasseService
from edupaie.services.echeancier_service import EcheancierService
from edupaie.services.ecole import courant, definir
from edupaie.services.ecole_service import EcoleService
from edupaie.services.eleve_service import EleveService
from edupaie.services.frais_service import FraisService
from edupaie.services.import_service import ImportEleveService
from edupaie.services.paiement_service import PaiementService
from edupaie.services.remise_service import RemiseService
from edupaie.services.sauvegarde_service import SauvegardeService
from edupaie.services.verification_service import VerificationService
from edupaie.ui.animations import FonduDialogues
from edupaie.ui.boutons import ProtegeBoutons
from edupaie.ui.inactivite import DetecteurInactivite
from edupaie.ui.login_dialog import LoginDialog
from edupaie.ui.main_window import MainWindow
from edupaie.ui.theme import style_pour

DELAI_INACTIVITE_MS = 5 * 60 * 1000  # 5 minutes


def preparer_dossier_de_travail():
    """Version installée : reçus et données vont dans %LOCALAPPDATA%\\EduPaie."""
    if getattr(sys, "frozen", False):
        dossier = dossier_donnees()
        dossier.mkdir(parents=True, exist_ok=True)
        os.chdir(dossier)


def sauvegarder_sans_bloquer(service):
    """Une sauvegarde ratée ne doit jamais empêcher d'ouvrir ou de fermer l'application."""
    try:
        service.sauvegarde_auto()
    except Exception as e:
        print("Sauvegarde automatique impossible :", e, file=sys.stderr)


def main():
    preparer_dossier_de_travail()
    initialiser_base()

    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.setStyle("Fusion")
    protege_boutons = ProtegeBoutons(app)
    fondu = FonduDialogues(app)
    app.installEventFilter(fondu)
    app.installEventFilter(protege_boutons)

    conn = get_connection()
    eleves = EleveRepository(conn)
    paiements = PaiementRepository(conn)

    # Services « internes » (non journalisés)
    auth = AuthService(UtilisateurRepository(conn), CodeSecoursRepository(conn))
    journal = JournalService(JournalRepository(conn), auth)
    frais = FraisService(FraisRepository(conn), auth)
    sauvegarde = SauvegardeService(auth)
    caisse = CaisseService(paiements, auth)
    remises = RemiseService(RemiseRepository(conn), eleves, paiements, auth)
    echeancier = EcheancierService(
        EcheanceRepository(conn), eleves, paiements, ContactRepository(conn), auth)
    sauvegarder_sans_bloquer(sauvegarde)  # au lancement
    ecole = EcoleService(EcoleRepository(conn), auth)
    definir(ecole.lire())
    app.setStyleSheet(style_pour(courant().couleur))
    gestion_classes = ClasseService(ClasseRepository(conn), auth)
    importation = ImportEleveService(ImportRepository(conn), eleves, frais, auth, sauvegarde)
    verif = VerificationService(VerificationRepository(conn), auth)
    verification.definir_cle(verif.cle())  # clé des codes de contrôle des reçus
    annees = AnneeService(AnneeRepository(conn), ClasseRepository(conn), auth, sauvegarde)

    # Services affichés à l'écran : enveloppés pour alimenter le journal d'audit
    def audite(service, regles):
        return Audite(service, journal, regles)

    auth_ui = audite(auth, audit_regles.regles_auth())
    eleve_service = audite(EleveService(eleves), audit_regles.regles_eleve())
    paiement_service = audite(
        PaiementService(eleves, paiements, auth, annee_active=annees.active),
        audit_regles.regles_paiement())
    frais_ui = audite(frais, audit_regles.regles_frais())
    sauvegarde_ui = audite(sauvegarde, audit_regles.regles_sauvegarde())
    remises_ui = audite(remises, audit_regles.regles_remise())
    echeancier_ui = audite(echeancier, audit_regles.regles_echeancier())
    ecole_ui = audite(ecole, audit_regles.regles_ecole())
    importation_ui = audite(importation, audit_regles.regles_import())
    classes_ui = audite(gestion_classes, audit_regles.regles_classe())
    verif_ui = audite(verif, audit_regles.regles_verification())
    annees_ui = audite(annees, audit_regles.regles_annee())

    # Connexion obligatoire, répétée après chaque déconnexion ou verrouillage
    while True:
        login = LoginDialog(auth_ui)
        login.show()
        login.raise_()
        login.activateWindow()
        if login.exec() != QDialog.Accepted:
            break

        fenetre = MainWindow(
            eleve_service, paiement_service, auth_ui, frais_ui, sauvegarde_ui,
            caisse, remises_ui, echeancier_ui, ecole_ui, importation_ui,
            classe_service=classes_ui, journal_service=journal,
            verification_service=verif_ui, annee_service=annees_ui,
        )
        fenetre.resize(1180, 720)
        fenetre.showMaximized()

        detecteur = DetecteurInactivite(DELAI_INACTIVITE_MS, fenetre.deconnecter)
        app.installEventFilter(detecteur)

        app.exec()

        app.removeEventFilter(detecteur)
        detecteur.arreter()
        auth.deconnecter()
        if not fenetre.deconnexion:  # fenêtre fermée normalement : on quitte
            break

    sauvegarder_sans_bloquer(sauvegarde)  # à la fermeture
    sys.exit(0)


if __name__ == "__main__":
    main()