import re
import unicodedata
from dataclasses import dataclass
from html import escape

from edupaie.services.licence import SUPPORT_EMAIL, SUPPORT_WHATSAPP

# Identifiant d'écran -> titre exact de l'entrée du menu
ECRANS = {
    "eleves": "Élèves", "dashboard": "Tableau de bord", "verifier": "Vérifier un reçu",
    "impayes": "Impayés", "caisse": "Clôture de caisse", "annees": "Années scolaires",
    "classes": "Classes", "frais": "Classes et frais", "utilisateurs": "Utilisateurs",
    "journal": "Journal d'audit", "sauvegardes": "Sauvegardes", "licence": "Licence",
    "parametres": "Paramètres", "guide": "Guide d'utilisation",
}

ORDRE_CATEGORIES = ["Pour commencer", "Au quotidien", "Élèves",
                    "Configuration de l'école", "Administration", "Aide"]

MOTS_VIDES = {"un", "une", "le", "la", "les", "de", "du", "des", "d", "l", "a", "en",
              "et", "ou", "au", "aux", "mon", "ma", "mes", "je", "comment"}


@dataclass(frozen=True)
class Article:
    id: str
    categorie: str
    titre: str
    corps: str                      # HTML simple
    permission: str | None = None   # l'article n'est proposé qu'à ceux qui ont ce droit
    mots_cles: str = ""             # pour la recherche
    ecran: str | None = None        # identifiant d'écran : bouton « Ouvrir l'écran »


def _g(id_article, texte):
    return f'<a href="guide:{id_article}">{texte}</a>'


def _e(id_ecran, texte=None):
    return f'<a href="ecran:{id_ecran}">{texte or ECRANS[id_ecran]}</a>'


def _note(texte):
    return ('<table width="100%" cellpadding="8" style="background-color:#eef2ff">'
            f'<tr><td><b>Astuce :</b> {texte}</td></tr></table><p></p>')


def _attention(texte):
    return ('<table width="100%" cellpadding="8" style="background-color:#fff7ed">'
            f'<tr><td><b>Attention :</b> {texte}</td></tr></table><p></p>')


ARTICLES = [
    # ------------------------------------------------------------------ Pour commencer
    Article(
        "connexion", "Pour commencer", "Se connecter et se déconnecter",
        "<p>Au lancement, saisis ton <b>identifiant</b> et ton <b>mot de passe</b>, puis "
        "clique sur « Se connecter ».</p>"
        "<ul>"
        "<li>Si ton compte a été créé ou réinitialisé par un administrateur, le mot de "
        "passe est <b>temporaire</b> : EduPaie te demande d'en choisir un personnel (8 "
        "caractères minimum, avec une lettre et un chiffre).</li>"
        "<li>Après <b>5 erreurs</b> de suite, la connexion est bloquée jusqu'au "
        "redémarrage de l'application.</li>"
        "<li>Après <b>5 minutes</b> sans activité, EduPaie se verrouille : il faut se "
        "reconnecter. Cela protège les données quand tu t'éloignes du poste.</li>"
        "<li>« Se déconnecter » (en bas du menu) ferme ta session ; « Mon mot de passe » "
        "te permet de le changer quand tu veux.</li>"
        "</ul>"
        "<p>Mot de passe oublié ? Voir " + _g("mot_de_passe", "Mot de passe et codes de secours")
        + ".</p>",
        mots_cles="connexion identifiant mot de passe verrouillage inactivité bloqué "
                  "déconnexion temporaire"),
    Article(
        "ecran", "Pour commencer", "Comprendre l'écran",
        "<ul>"
        "<li>Le <b>menu de gauche</b> liste les écrans auxquels ton rôle donne accès : un "
        "comptable ne voit pas « Utilisateurs », par exemple.</li>"
        "<li>Un <b>bandeau coloré</b> en haut de l'écran signale l'état de la licence "
        "(essai en cours, licence bientôt expirée, mode consultation).</li>"
        "<li>Un bouton <b>grisé</b> signifie que ton rôle n'a pas ce droit.</li>"
        "<li>Les statuts des élèves : <b>Soldé</b> (vert), <b>Partiellement payé</b> "
        "(orange), <b>Non payé</b> (rouge).</li>"
        "<li>La touche <b>F1</b> ouvre ce guide à tout moment.</li>"
        "</ul>",
        mots_cles="menu bandeau bouton grisé statut couleur aide f1"),
    Article(
        "premier_lancement", "Pour commencer", "Premier lancement d'une école",
        "<p>Au tout premier lancement, EduPaie te demande de créer le compte "
        "<b>administrateur</b>.</p>"
        "<ol>"
        "<li>Saisis ton nom complet, un identifiant, un mot de passe (8 caractères minimum, "
        "avec une lettre et un chiffre) et sa confirmation.</li>"
        "<li>Les <b>8 codes de secours</b> s'affichent une seule fois : clique sur « "
        "Imprimer la feuille (PDF) » et range la feuille dans un endroit sûr (coffre, "
        "armoire fermée). Ils te permettront de récupérer ton compte si tu oublies ton "
        "mot de passe.</li>"
        "<li>Crée un <b>second compte administrateur</b> dans l'écran Utilisateurs : c'est "
        "ton filet de sécurité.</li>"
        "<li>Suis la liste « Pour bien démarrer » de ce guide.</li>"
        "</ol>",
        permission="utilisateur.gerer", ecran="utilisateurs",
        mots_cles="installation premier lancement administrateur codes de secours démarrage"),
    # ------------------------------------------------------------------ Au quotidien
    Article(
        "paiement", "Au quotidien", "Enregistrer un paiement",
        "<ol>"
        "<li>Ouvre l'écran Élèves et cherche l'élève (nom ou prénom).</li>"
        "<li>Sélectionne-le et clique sur « Enregistrer un paiement » (ou ouvre sa "
        "fiche).</li>"
        "<li>Saisis le <b>montant</b>, la <b>date</b> et le <b>mode</b> : espèces, chèque, "
        "virement ou mobile money.</li>"
        "<li>Valide : le paiement est enregistré, le solde et le statut sont mis à jour, "
        "et un reçu numéroté (REC-année-numéro) est créé.</li>"
        "</ol>"
        + _attention("Le montant doit être un nombre entier, ne peut pas dépasser le solde "
                     "restant, et la date ne peut pas être dans le futur. Un élève déjà "
                     "soldé n'accepte plus de paiement.")
        + "<p>Une erreur de saisie ? Voir " + _g("annuler_paiement", "Annuler un paiement")
        + ".</p>",
        permission="paiement.encaisser", ecran="eleves",
        mots_cles="encaisser payer paiement caisse espèces chèque virement mobile money reçu"),
    Article(
        "recu", "Au quotidien", "Retrouver et imprimer un reçu",
        "<p>Tous les reçus d'un élève sont dans sa fiche.</p>"
        "<ol>"
        "<li>Sélectionne l'élève puis « Fiche et Historique » (ou double-clique sur sa "
        "ligne).</li>"
        "<li>Sélectionne le paiement et clique sur « Voir / imprimer le reçu » (ou "
        "double-clique sur la ligne).</li>"
        "<li>Le reçu s'ouvre en PDF : imprime-le ou enregistre-le.</li>"
        "</ol>"
        "<p>Le reçu indique l'école (nom, logo, adresse), l'élève, le montant, la date, le "
        "mode, le solde restant, le caissier, un <b>QR code</b> et un <b>code de "
        "contrôle</b>. Un paiement annulé porte la mention « REÇU ANNULÉ ».</p>"
        + _note("On ne modifie jamais un reçu : en cas d'erreur, on annule le paiement et "
                "on en saisit un nouveau."),
        permission="paiement.lire", ecran="eleves",
        mots_cles="reçu imprimer pdf duplicata historique"),
    Article(
        "verifier", "Au quotidien", "Vérifier qu'un reçu est authentique",
        "<p>Chaque reçu PDF porte un <b>QR code</b> et un <b>code de contrôle</b> (par "
        "exemple A1B2C-3D4E5). L'écran Vérifier un reçu confirme qu'un reçu présenté par "
        "un parent est vrai.</p>"
        "<ol>"
        "<li>Ouvre l'écran et place le curseur dans la case.</li>"
        "<li>Avec une <b>douchette USB</b> : scanne le QR code du reçu. Sans douchette : "
        "tape le numéro du reçu, un espace, puis le code de contrôle.</li>"
        "<li>Appuie sur Entrée : la réponse s'affiche en grand.</li>"
        "</ol>"
        "<ul>"
        "<li><b>Authentique</b> : le reçu existe et son code est valide.</li>"
        "<li><b>Annulé</b> : le paiement a été annulé, le reçu ne prouve plus rien.</li>"
        "<li><b>Falsifié ou modifié</b> : le code ne correspond pas aux données (montant "
        "retouché, code mal saisi). Ne l'accepte pas avant d'avoir vérifié.</li>"
        "<li><b>Introuvable</b> : aucun reçu avec ce numéro dans cette base.</li>"
        "<li><b>Code non vérifié</b> : seul le numéro a été saisi ; compare les "
        "informations avec le papier.</li>"
        "</ul>"
        + _note("Un téléphone qui scanne le QR code n'affiche que du texte : la "
                "vérification se fait dans EduPaie. Les tentatives douteuses sont écrites "
                "dans le journal d'audit."),
        permission="paiement.lire", ecran="verifier",
        mots_cles="authentique faux reçu qr code douchette scanner falsifié contrôle"),
    Article(
        "annuler_paiement", "Au quotidien", "Annuler un paiement",
        "<p>Réservé à l'administrateur. Le paiement n'est jamais effacé : il reste visible, "
        "barré, et son reçu est marqué annulé.</p>"
        "<ol>"
        "<li>Ouvre la fiche de l'élève et sélectionne le paiement.</li>"
        "<li>Clique sur « Annuler le paiement ».</li>"
        "<li>Écris le <b>motif</b> (5 caractères minimum) et valide.</li>"
        "</ol>"
        "<p>Le solde de l'élève est recalculé et il peut de nouveau payer. L'annulation est "
        "écrite dans le journal d'audit.</p>",
        permission="paiement.annuler", ecran="eleves",
        mots_cles="annuler erreur montant corriger supprimer paiement motif"),
    Article(
        "cloture", "Au quotidien", "Faire la clôture de caisse",
        "<p>La clôture de caisse donne le total encaissé sur une période, par mode de "
        "paiement et par caissier.</p>"
        "<ol>"
        "<li>Ouvre « Clôture de caisse ».</li>"
        "<li>Choisis la période (boutons « Aujourd'hui » et « Ce mois », ou deux dates).</li>"
        "<li>Lis le tableau : un caissier par ligne, une colonne par mode, le total en "
        "bas.</li>"
        "<li>« Exporter en PDF » produit la feuille à signer (visa du caissier et de la "
        "direction) ; « Exporter en Excel » donne le détail paiement par paiement.</li>"
        "</ol>"
        "<p>L'administrateur voit tous les caissiers ; un comptable ne voit que ses propres "
        "encaissements. Les paiements annulés sont signalés mais ne sont pas comptés.</p>",
        permission="caisse.voir", ecran="caisse",
        mots_cles="clôture caisse journée total encaissé caissier pdf excel"),
    Article(
        "impayes", "Au quotidien", "Suivre les impayés et relancer les parents",
        "<p>L'écran Impayés liste les élèves en retard d'après l'<b>échéancier</b> de leur "
        "classe.</p>"
        "<ol>"
        "<li>Choisis la date et, si tu veux, une classe.</li>"
        "<li>Chaque ligne montre l'échéance impayée la plus ancienne, les jours de retard, "
        "le montant exigible, le payé, le montant en retard et le téléphone.</li>"
        "<li>Sélectionne un élève et clique sur « Relancer par WhatsApp » : WhatsApp "
        "s'ouvre avec un message prêt, à envoyer toi-même.</li>"
        "<li>« Exporter en PDF » ou « Exporter en Excel » donne la liste à imprimer.</li>"
        "</ol>"
        + _attention("Il faut le numéro du parent : « Modifier le contact » (ici ou dans la "
                     "fiche de l'élève). Les classes sans échéancier ne sont pas suivies : "
                     "définis-le dans « Classes et frais ».")
        + "<p>Voir aussi " + _g("frais", "Frais et échéancier") + ".</p>",
        permission="impayes.voir", ecran="impayes",
        mots_cles="impayés retard relance whatsapp parent téléphone échéance"),
    Article(
        "tableau_de_bord", "Au quotidien", "Lire le tableau de bord",
        "<p>Le tableau de bord résume la situation de l'<b>année active</b> : nombre "
        "d'élèves, total encaissé, total restant à payer, répartition entre élèves soldés, "
        "partiellement payés et non payés, et derniers paiements enregistrés. Les paiements "
        "annulés ne sont pas comptés.</p>"
        "<p>Pour voir une autre année, utilise le filtre d'année de l'écran Élèves.</p>",
        permission="dashboard.voir", ecran="dashboard",
        mots_cles="tableau de bord chiffres clés total encaissé statistiques"),
    # ------------------------------------------------------------------ Élèves
    Article(
        "eleves", "Élèves", "Chercher un élève et lire la liste",
        "<p>L'écran Élèves est le point de départ de la caisse.</p>"
        "<ul>"
        "<li>La <b>barre de recherche</b> filtre par nom ou prénom pendant que tu tapes.</li>"
        "<li>Trois filtres : l'<b>année scolaire</b> (l'année active par défaut, ou « "
        "Toutes les années »), la <b>classe</b> et le <b>statut</b>.</li>"
        "<li>Chaque ligne affiche le total dû (remises déduites), le payé, le solde et le "
        "statut. Double-clique sur une ligne pour ouvrir la fiche de l'élève.</li>"
        "</ul>"
        "<p>Les boutons du bas : Ajouter, Modifier, Supprimer, Enregistrer un paiement, "
        "Fiche et Historique, Exporter vers Excel, Importer depuis Excel. Ceux que ton rôle "
        "n'autorise pas sont grisés.</p>",
        permission="eleve.lire", ecran="eleves",
        mots_cles="liste élèves recherche filtre classe année statut"),
    Article(
        "eleve_ajouter", "Élèves", "Ajouter ou modifier un élève",
        "<ol>"
        "<li>Clique sur « Ajouter » (ou sur « Modifier » après avoir sélectionné un "
        "élève).</li>"
        "<li>Saisis le nom et le prénom, choisis la <b>classe</b> dans la liste et "
        "l'<b>année scolaire</b>.</li>"
        "<li>Le <b>total des frais</b> se remplit tout seul d'après les frais de la classe "
        "(le détail s'affiche au-dessus). Tu peux le modifier si l'élève a un tarif "
        "particulier.</li>"
        "<li>Enregistre.</li>"
        "</ol>"
        + _attention("Quand tu modifies la classe d'un élève existant, son total n'est pas "
                     "recalculé : vérifie-le. La suppression d'un élève est refusée s'il a "
                     "des paiements, qui doivent rester dans la comptabilité."),
        permission="eleve.ecrire", ecran="eleves",
        mots_cles="ajouter nouvel élève inscrire modifier classe supprimer total frais"),
    Article(
        "fiche", "Élèves", "Utiliser la fiche d'un élève",
        "<p>La fiche regroupe tout sur un élève : classe, année, statut, trois chiffres "
        "clés (frais annuels, total réglé, solde restant), l'<b>historique des "
        "paiements</b>, les <b>remises et bourses</b> et les boutons d'action.</p>"
        "<ul>"
        "<li><b>Enregistrer un paiement</b> et <b>Voir / imprimer le reçu</b> (aussi par "
        "double-clic sur un paiement).</li>"
        "<li>Une ligne barrée « ANNULÉ » est un paiement annulé : survole-la pour voir qui "
        "l'a annulé et pourquoi.</li>"
        "<li><b>Contact du parent</b> : nom et téléphone du parent ou tuteur, utilisés "
        "pour les relances WhatsApp (8 chiffres pour le Togo, ou numéro avec l'indicatif, "
        "par exemple +233 24 123 4567).</li>"
        "</ul>",
        permission="eleve.lire", ecran="eleves",
        mots_cles="fiche historique paiements contact parent téléphone tuteur"),
    Article(
        "remises", "Élèves", "Accorder une remise ou une bourse",
        "<p>Une remise réduit ce que doit l'élève (fratrie, bourse, exonération). Réservé "
        "à l'administrateur.</p>"
        "<ol>"
        "<li>Ouvre la fiche de l'élève et clique sur « Accorder une remise ».</li>"
        "<li>Choisis le type : <b>montant</b> en FCFA ou <b>pourcentage</b> du total, et "
        "saisis la valeur (le montant calculé s'affiche).</li>"
        "<li>Choisis ou écris le <b>motif</b> (obligatoire).</li>"
        "</ol>"
        "<p>Une remise ne peut pas dépasser le solde restant. Pour la retirer : « Annuler "
        "la remise » avec un motif ; elle reste visible, barrée. Dans les deux cas, les "
        "soldes sont recalculés.</p>",
        permission="remise.gerer", ecran="eleves",
        mots_cles="remise bourse fratrie exonération réduction pourcentage"),
    Article(
        "import", "Élèves", "Importer des élèves depuis Excel",
        "<p>Pour enregistrer toute une école d'un coup. Réservé à l'administrateur.</p>"
        "<ol>"
        "<li>Écran Élèves → « Importer depuis Excel ».</li>"
        "<li>Clique sur « Télécharger le modèle Excel » et remplis-le : une ligne par "
        "élève. <b>Nom, Prénom et Classe</b> sont obligatoires ; Année scolaire, Total dû "
        "(FCFA), Parent / tuteur et Téléphone sont facultatifs.</li>"
        "<li>Enregistre le fichier au format <b>.xlsx</b>, puis « Choisir le fichier... ».</li>"
        "<li>Lis l'aperçu : lignes à importer, lignes ignorées (déjà enregistrées) et "
        "lignes en erreur (en rouge, avec la raison).</li>"
        "<li>Clique sur « Importer N élève(s) ».</li>"
        "</ol>"
        + _note("Si le total est vide, EduPaie utilise les frais définis pour la classe. "
                "Une sauvegarde est faite juste avant l'import. Tu peux corriger le fichier "
                "et le réimporter : les élèves déjà enregistrés sont ignorés, il n'y a pas "
                "de doublon."),
        permission="eleve.importer", ecran="eleves",
        mots_cles="importer excel xlsx modèle fichier liste élèves"),
    Article(
        "export", "Élèves", "Exporter vers Excel ou PDF",
        "<p>La plupart des listes s'exportent pour être ouvertes dans Excel ou "
        "LibreOffice :</p>"
        "<ul>"
        "<li>Écran Élèves : « Exporter vers Excel » (la liste telle qu'elle est "
        "filtrée).</li>"
        "<li>Clôture de caisse, Impayés, Journal d'audit : « Exporter en Excel » ; la "
        "clôture et les impayés existent aussi en PDF.</li>"
        "</ul>"
        "<p>Le fichier s'ouvre directement dans Excel s'il est installé. Sinon, EduPaie "
        "t'indique où le trouver (dossier « exports »). Chaque export porte la date et "
        "l'heure dans son nom : rien n'est écrasé.</p>",
        permission="eleve.lire", ecran="eleves",
        mots_cles="export excel pdf tableur liste imprimer"),
    # ------------------------------------------------------------------ Configuration
    Article(
        "parametres", "Configuration de l'école", "Régler les informations et la couleur de l'école",
        "<p>Ces informations apparaissent en haut de tous les reçus et PDF. Réservé à "
        "l'administrateur.</p>"
        "<ul>"
        "<li><b>Nom, adresse, boîte postale, téléphone, e-mail</b> : saisis-les tels "
        "qu'ils doivent être imprimés (« 1234 » devient « BP 1234 »).</li>"
        "<li><b>Logo</b> : « Choisir un logo... » (il est réduit automatiquement).</li>"
        "<li><b>Couleur</b> : choisis l'une des propositions ou « Autre couleur... ». "
        "L'application change aussitôt de couleur ; une couleur trop claire est assombrie "
        "pour que le texte reste lisible. « Couleur d'origine » revient à celle "
        "d'EduPaie.</li>"
        "</ul>"
        "<p>Clique sur « Aperçu du reçu » pour voir le résultat, puis sur « Enregistrer ». "
        "Si tu quittes l'écran sans enregistrer, la couleur revient à celle "
        "enregistrée.</p>",
        permission="ecole.gerer", ecran="parametres",
        mots_cles="école nom adresse boîte postale logo couleur charte graphique reçu"),
    Article(
        "classes", "Configuration de l'école", "Gérer les classes",
        "<p>Les classes alimentent toutes les listes de choix. Réservé à "
        "l'administrateur.</p>"
        "<ul>"
        "<li><b>Ajouter des classes...</b> : écris une classe par ligne, ou génère une "
        "série (niveau « 6e » + sections « A B C D » donne 6e A, 6e B, 6e C, 6e D).</li>"
        "<li><b>Renommer</b> : le nouveau nom est aussi appliqué aux élèves, aux frais et à "
        "l'échéancier.</li>"
        "<li><b>Monter / Descendre</b> : l'ordre choisi est celui des listes et sert à "
        "proposer la classe supérieure lors du passage à l'année suivante.</li>"
        "<li><b>Supprimer</b> : impossible tant que des élèves, des frais ou des tranches "
        "utilisent la classe.</li>"
        "</ul>",
        permission="classe.gerer", ecran="classes",
        mots_cles="classes ajouter série renommer supprimer ordre niveau section"),
    Article(
        "frais", "Configuration de l'école", "Définir les frais et l'échéancier",
        "<p>Chaque classe a des lignes de frais saisies par l'école (inscription, "
        "scolarité, examen, uniforme...). Le total d'un nouvel élève s'en déduit. Réservé "
        "à l'administrateur.</p>"
        "<ol>"
        "<li>Choisis la classe et l'année scolaire.</li>"
        "<li>« Ajouter une ligne » : libellé et montant. Modifie ou supprime avec les "
        "autres boutons.</li>"
        "<li>« Copier vers une autre classe » reprend les lignes pour gagner du temps.</li>"
        "</ol>"
        "<h3>Échéancier</h3>"
        "<p>« Échéancier de la classe » découpe le total en <b>tranches</b> (nom, date "
        "limite, part en %). Le total doit faire 100 %. Il sert à calculer les retards de "
        "l'écran Impayés.</p>"
        + _note("Changer les frais d'une classe ne modifie pas les élèves déjà enregistrés "
                "ni leurs paiements : seuls les nouveaux élèves reçoivent le nouveau "
                "total."),
        permission="frais.gerer", ecran="frais",
        mots_cles="frais scolarité inscription échéancier tranches montant tarif"),
    Article(
        "annees", "Configuration de l'école", "Passer à l'année scolaire suivante",
        "<p>À la fin de l'année scolaire, EduPaie prépare l'année suivante sans rien "
        "perdre. Réservé à l'administrateur.</p>"
        "<ol>"
        "<li>Vérifie les frais de la nouvelle année dans « Classes et frais », ou clique "
        "sur « Reprendre les frais et échéanciers de l'année précédente » (écran Années "
        "scolaires).</li>"
        "<li>Clique sur « Préparer le passage à l'année suivante... ».</li>"
        "<li>Pour chaque élève, vérifie la nouvelle classe proposée et décoche ceux qui "
        "partent (« Sortie »). « Appliquer à toute la classe » fait gagner du temps.</li>"
        "<li>Choisis de reporter ou non les <b>arriérés</b> sur la nouvelle année.</li>"
        "<li>« Lancer le passage » : une sauvegarde est faite, les élèves reçoivent une "
        "nouvelle fiche, un rapport Excel est proposé.</li>"
        "</ol>"
        "<p>Les anciennes fiches, leurs paiements et leurs reçus restent consultables avec "
        "le filtre d'année de l'écran Élèves. Quand l'arriéré est reporté, l'ancienne fiche "
        "est soldée par une remise « Arriéré reporté ».</p>",
        permission="annee.gerer", ecran="annees",
        mots_cles="année scolaire passage réinscription rentrée arriérés redoublement"),
    # ------------------------------------------------------------------ Administration
    Article(
        "utilisateurs", "Administration", "Gérer les utilisateurs et les rôles",
        "<p>Chaque personne qui utilise EduPaie a son compte. Réservé à "
        "l'administrateur.</p>"
        "<ul>"
        "<li><b>Ajouter un utilisateur</b> : identifiant, nom, rôle et mot de passe "
        "<b>temporaire</b> (il devra en choisir un à sa première connexion).</li>"
        "<li><b>Réinitialiser le mot de passe</b> : quand quelqu'un a oublié le sien.</li>"
        "<li><b>Supprimer</b> : impossible pour ton propre compte et pour le dernier "
        "administrateur.</li>"
        "</ul>"
        "<h3>Les trois rôles</h3>"
        "<table border='1' cellspacing='0' cellpadding='6'>"
        "<tr><th>Fonction</th><th>Administrateur</th><th>Comptable</th><th>Lecture</th></tr>"
        "<tr><td>Consulter élèves, paiements, tableau de bord</td><td>oui</td><td>oui</td>"
        "<td>oui</td></tr>"
        "<tr><td>Ajouter ou modifier un élève</td><td>oui</td><td>oui</td><td>non</td></tr>"
        "<tr><td>Enregistrer un paiement</td><td>oui</td><td>oui</td><td>non</td></tr>"
        "<tr><td>Clôture de caisse et impayés</td><td>oui (tous les caissiers)</td>"
        "<td>oui (ses encaissements)</td><td>non</td></tr>"
        "<tr><td>Supprimer un élève, annuler un paiement, remises, import</td><td>oui</td>"
        "<td>non</td><td>non</td></tr>"
        "<tr><td>Classes, frais, école, années, utilisateurs, sauvegardes, journal, "
        "licence</td><td>oui</td><td>non</td><td>non</td></tr>"
        "</table>"
        "<p></p>"
        + _attention("Crée toujours <b>deux comptes administrateur</b> : si le seul "
                     "administrateur perd son mot de passe et ses codes de secours, plus "
                     "personne ne peut gérer les comptes."),
        permission="utilisateur.gerer", ecran="utilisateurs",
        mots_cles="utilisateurs comptes rôles droits administrateur comptable lecture "
                  "caissier permissions"),
    Article(
        "mot_de_passe", "Administration", "Mot de passe et codes de secours",
        "<h3>Changer mon mot de passe</h3>"
        "<p>« Mon mot de passe » (en bas du menu) : saisis l'ancien, le nouveau (8 "
        "caractères minimum, avec une lettre et un chiffre) et sa confirmation.</p>"
        "<h3>J'ai oublié mon mot de passe</h3>"
        "<ul>"
        "<li><b>Tu es administrateur</b> : sur l'écran de connexion, clique sur « Mot de "
        "passe oublié ? », saisis ton identifiant, <b>un de tes 8 codes de secours</b> et "
        "un nouveau mot de passe. Chaque code ne sert qu'une fois ; 5 essais ratés "
        "bloquent la récupération.</li>"
        "<li><b>Tu n'es pas administrateur</b> : demande à un administrateur de "
        "réinitialiser ton mot de passe. Tu recevras un mot de passe temporaire que tu "
        "changeras à ta connexion.</li>"
        "</ul>"
        "<h3>Les codes de secours (administrateurs)</h3>"
        "<p>Écran Utilisateurs → « Mes codes de secours » (ton mot de passe est demandé) : "
        "8 nouveaux codes sont créés, les anciens sont invalidés. Ils ne sont affichés "
        "qu'une fois : imprime la feuille.</p>"
        + _attention("Quiconque possède un de ces codes peut prendre le contrôle du compte "
                     "administrateur : range la feuille sous clé, jamais à côté de "
                     "l'ordinateur."),
        mots_cles="mot de passe oublié codes de secours récupérer réinitialiser changer"),
    Article(
        "sauvegardes", "Administration", "Sauvegarder et restaurer les données",
        "<ul>"
        "<li><b>Automatique</b> : une copie est faite à l'ouverture et à la fermeture de "
        "l'application quand les données ont changé. Les 30 dernières sont conservées.</li>"
        "<li><b>Manuelle</b> : « Sauvegarder maintenant ».</li>"
        "<li><b>Sur une clé USB</b> : « Copier vers une clé USB / un dossier… ».</li>"
        "<li><b>Restaurer</b> : sélectionne une sauvegarde puis « Restaurer la sélection ». "
        "Une copie des données actuelles est faite avant, puis l'application se ferme : "
        "relance-la.</li>"
        "</ul>"
        + _attention("Restaurer une ancienne sauvegarde fait perdre les saisies faites "
                     "depuis, et ramène aussi l'ancien journal d'audit.")
        + _note("Copie régulièrement une sauvegarde sur une clé USB ou un disque externe : "
                "si l'ordinateur tombe en panne, le dossier des sauvegardes tombe avec "
                "lui."),
        permission="sauvegarde.gerer", ecran="sauvegardes",
        mots_cles="sauvegarde restaurer copie clé usb données perte panne"),
    Article(
        "journal", "Administration", "Consulter le journal d'audit",
        "<p>Le journal note <b>qui a fait quoi et quand</b> : connexions et échecs, "
        "élèves créés, modifiés ou supprimés (avec l'ancienne et la nouvelle valeur), "
        "paiements, annulations, remises, frais, comptes, sauvegardes, paramètres...</p>"
        "<ul>"
        "<li>Filtre par dates, type d'action, utilisateur ou texte.</li>"
        "<li>Les lignes en <b>rouge</b> sont sensibles : suppression, annulation, échec de "
        "connexion, restauration, récupération de mot de passe, reçu douteux.</li>"
        "<li>« Vérifier l'intégrité » contrôle que personne n'a modifié ni supprimé une "
        "ligne du journal.</li>"
        "<li>« Exporter en Excel » en fait un fichier.</li>"
        "</ul>"
        "<p>Les mots de passe et les codes de secours ne sont jamais écrits dans le "
        "journal.</p>",
        permission="audit.voir", ecran="journal",
        mots_cles="journal audit historique qui a fait contrôle fraude intégrité"),
    Article(
        "licence", "Administration", "Licence : essai, activation, renouvellement",
        "<p>EduPaie s'utilise gratuitement pendant <b>30 jours</b>, puis avec une "
        "<b>licence</b> fournie par ton fournisseur.</p>"
        "<ul>"
        "<li><b>Essai</b> : tout fonctionne, un bandeau indique les jours restants.</li>"
        "<li><b>Licence valide</b> : aucun bandeau, sauf un avertissement 30 jours avant "
        "la fin.</li>"
        "<li><b>Mode consultation</b> (essai terminé ou licence expirée) : tu peux "
        "consulter, exporter, sauvegarder et vérifier un reçu, mais plus rien ne "
        "s'enregistre. Tes données ne sont jamais perdues.</li>"
        "</ul>"
        "<h3>Activer une licence</h3>"
        "<ol>"
        "<li>Écran Licence : copie l'<b>identifiant de cet ordinateur</b> (bouton « Copier »), "
        "ou clique sur « Demander une licence » (WhatsApp prérempli).</li>"
        "<li>Ton fournisseur te renvoie une clé ou un fichier .licence.</li>"
        "<li>« Activer une licence... » : colle la clé ou charge le fichier. L'application "
        "se rouvre : reconnecte-toi.</li>"
        "</ol>"
        "<p>Une licence est liée à un ordinateur. Si tu changes de PC ou réinstalles "
        "Windows, l'identifiant change : demande une nouvelle licence.</p>",
        permission="licence.gerer", ecran="licence",
        mots_cles="licence essai activation clé expiration renouvellement ordinateur "
                  "mode consultation"),
    # ------------------------------------------------------------------ Aide
    Article(
        "faq", "Aide", "Questions fréquentes",
        "<h3>J'ai saisi un mauvais montant.</h3>"
        "<p>Un administrateur annule le paiement (fiche de l'élève → « Annuler le "
        "paiement », avec un motif), puis tu saisis le bon. On ne modifie jamais un "
        "reçu.</p>"
        "<h3>Un élève est dans la mauvaise classe.</h3>"
        "<p>Écran Élèves → « Modifier ». Son total n'est pas recalculé : vérifie-le.</p>"
        "<h3>Je ne vois pas un écran ou un bouton est grisé.</h3>"
        "<p>Ton rôle n'a pas ce droit, ou la licence est expirée (mode consultation). "
        "Demande à un administrateur.</p>"
        "<h3>Plusieurs caissiers peuvent-ils travailler en même temps ?</h3>"
        "<p>Chacun a son compte, mais EduPaie fonctionne sur <b>un seul ordinateur</b> : "
        "ce n'est pas un logiciel en réseau. Deux ordinateurs auraient deux bases "
        "séparées.</p>"
        "<h3>L'export Excel s'ouvre dans un autre programme.</h3>"
        "<p>EduPaie cherche Excel ou LibreOffice. S'il n'en trouve pas, il te donne "
        "l'emplacement du fichier : ouvre-le avec ton tableur.</p>"
        "<h3>L'électricité a coupé pendant que je travaillais.</h3>"
        "<p>Chaque opération est enregistrée au moment où tu la valides. Relance "
        "l'application et vérifie la dernière saisie. Les sauvegardes automatiques "
        "protègent le reste.</p>"
        "<h3>On change d'ordinateur.</h3>"
        "<p>Installe EduPaie sur le nouveau, restaure la dernière sauvegarde (copiée sur "
        "une clé USB), puis demande une licence pour le nouvel ordinateur.</p>",
        mots_cles="faq questions erreur classe plusieurs caissiers réseau excel coupure "
                  "électricité changer ordinateur"),
    Article(
        "glossaire", "Aide", "Glossaire",
        "<ul>"
        "<li><b>Total dû</b> : ce que l'élève doit pour l'année, remises déduites.</li>"
        "<li><b>Solde</b> : ce qu'il reste à payer (total dû moins payé).</li>"
        "<li><b>Statut</b> : Soldé (tout payé), Partiellement payé, Non payé.</li>"
        "<li><b>Remise</b> : réduction accordée à un élève (bourse, fratrie...), avec un "
        "motif.</li>"
        "<li><b>Arriéré</b> : somme restant due à la fin d'une année.</li>"
        "<li><b>Échéancier</b> : découpage du total en tranches avec des dates limites.</li>"
        "<li><b>Tranche</b> : une part du total à payer avant une date.</li>"
        "<li><b>Clôture de caisse</b> : total encaissé sur une période, par caissier et par "
        "mode de paiement.</li>"
        "<li><b>Année active</b> : l'année affichée par défaut dans l'application.</li>"
        "<li><b>Code de contrôle</b> : code imprimé sur le reçu, qui prouve qu'il est "
        "authentique.</li>"
        "<li><b>Code de secours</b> : code à usage unique qui permet à un administrateur "
        "de récupérer son compte.</li>"
        "<li><b>Mode consultation</b> : mode sans saisie, quand l'essai est terminé ou la "
        "licence expirée.</li>"
        "</ul>",
        mots_cles="glossaire définitions vocabulaire solde arriéré tranche statut"),
    Article(
        "probleme", "Aide", "Que faire en cas de problème ?",
        "<ol>"
        "<li><b>Note le message exact</b> affiché à l'écran (ou prends-le en photo).</li>"
        "<li><b>Ne supprime rien</b> et ne réinstalle pas : tes données sont dans la "
        "base et dans les sauvegardes.</li>"
        "<li>Un administrateur peut consulter le journal d'audit pour retrouver ce qui "
        "s'est passé.</li>"
        "<li>Contacte ton fournisseur avec le message noté et, s'il existe, le fichier "
        "<b>erreurs.log</b> du dossier %LOCALAPPDATA%\\EduPaie (tape ce chemin dans la barre "
        "d'adresse de l'Explorateur de fichiers).</li>"
        "</ol>"
        "{support}",
        mots_cles="problème erreur bug aide support contact panne"),

    Article(
        "resume_jour", "Au quotidien", "Envoyer le résumé de la journée au directeur",
        "<p>À la fin de la journée, le comptable peut envoyer un résumé de ses encaissements "
        "au directeur par WhatsApp.</p>"
        "<ol>"
        "<li>Ouvre « Clôture de caisse » et vérifie la période (« Aujourd'hui » par "
        "défaut).</li>"
        "<li>Clique sur « Résumé par WhatsApp » : WhatsApp s'ouvre avec le message déjà "
        "écrit.</li>"
        "<li>Relis-le, puis appuie sur Envoyer dans WhatsApp. <b>Rien n'est envoyé "
        "tant que tu n'as pas appuyé sur Envoyer.</b></li>"
        "</ol>"
        "<p>Le message donne le total encaissé, le détail par mode de paiement et par "
        "caissier, les paiements annulés (avec leur motif) et, pour l'administrateur, les "
        "remises accordées. Un comptable ne résume que ses propres encaissements.</p>"
        "<ul>"
        "<li><b>Numéro de la direction</b> : l'administrateur l'enregistre une fois avec le "
        "bouton « Numéro de la direction... ». Sans numéro, tu choisis le destinataire (ou "
        "un groupe) dans WhatsApp.</li>"
        "<li><b>Pas de WhatsApp ou pas d'internet</b> : « Copier le message » le place dans "
        "le presse-papiers, pour le coller dans un SMS ou un e-mail.</li>"
        "</ul>"
        + _note("EduPaie n'envoie rien tout seul : quelqu'un doit cliquer chaque jour. Pour "
                "voir le détail complet, le directeur consulte le journal d'audit sur le poste "
                "de la caisse.")
        + "<p>Voir aussi " + _g("cloture", "Faire la clôture de caisse") + ".</p>",
        permission="caisse.voir", ecran="caisse",
        mots_cles="résumé whatsapp directeur rapport journée envoyer message comptable"),
]


# ---------------------------------------------------------------------- Service
def _cle(texte) -> str:
    """Forme comparable : sans accents, sans majuscules, sans ponctuation."""
    texte = unicodedata.normalize("NFD", str(texte or "").casefold())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


def _texte_brut(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _style(couleur: str) -> str:
    return "<style>h1, h2, h3, a { color: " + couleur + "; }</style>"


class GuideService:
    def __init__(self, auth=None, support_whatsapp=SUPPORT_WHATSAPP,
                 support_email=SUPPORT_EMAIL):
        self.auth = auth  # None : tous les articles
        self.support_whatsapp = support_whatsapp
        self.support_email = support_email
        self._index = {a.id: (_cle(a.titre), _cle(a.mots_cles), _cle(_texte_brut(a.corps)))
                       for a in ARTICLES}

    # --- Articles visibles selon le rôle -----------------------------------------------
    def _autorise(self, article) -> bool:
        return (article.permission is None or self.auth is None
                or self.auth.peut(article.permission))

    def articles(self) -> list[Article]:
        return [a for a in ARTICLES if self._autorise(a)]

    def article(self, identifiant):
        return next((a for a in self.articles() if a.id == identifiant), None)

    def par_categorie(self) -> list[tuple[str, list[Article]]]:
        visibles = self.articles()
        groupes = []
        for categorie in ORDRE_CATEGORIES:
            membres = [a for a in visibles if a.categorie == categorie]
            if membres:
                groupes.append((categorie, membres))
        return groupes

    # --- Recherche ----------------------------------------------------------------------
    def rechercher(self, texte) -> list[Article]:
        mots = [m for m in _cle(texte).split() if m not in MOTS_VIDES]
        if not mots:
            return []
        trouves = []
        for article in self.articles():
            titre, cles, corps = self._index[article.id]
            ensemble = f"{titre} {cles} {corps}"
            if not all(m in ensemble for m in mots):
                continue
            score = sum(1 + 5 * (m in titre) + 3 * (m in cles) for m in mots)
            trouves.append((-score, article.titre.casefold(), article))
        trouves.sort(key=lambda t: (t[0], t[1]))
        return [a for _, _, a in trouves]

    # --- Rendu ------------------------------------------------------------------------------
    def _support(self) -> str:
        coordonnees = []
        if self.support_whatsapp:
            coordonnees.append(f"WhatsApp : +{escape(self.support_whatsapp)}")
        if self.support_email:
            coordonnees.append(f"e-mail : {escape(self.support_email)}")
        if coordonnees:
            return "<p>Ton fournisseur : " + " - ".join(coordonnees) + ".</p>"
        return "<p>Contacte ton fournisseur EduPaie.</p>"

    def _rendre(self, corps: str) -> str:
        return corps.replace("{support}", self._support())

    def html(self, article, couleur: str) -> str:
        lien = ""
        if article.ecran:
            lien = (f'<p><a href="ecran:{article.ecran}">▶ Ouvrir l\'écran '
                    f'« {escape(ECRANS[article.ecran])} »</a></p>')
        return (_style(couleur) + f"<h2>{escape(article.titre)}</h2>"
                + self._rendre(article.corps) + lien)

    def html_demarrage(self, etapes: list[dict], couleur: str) -> str:
        obligatoires = [e for e in etapes if not e["facultatif"]]
        faites = sum(1 for e in obligatoires if e["fait"])
        lignes = []
        for e in etapes:
            marque = ('<span style="color:#166534">✔</span>' if e["fait"]
                      else '<span style="color:#9a3412">○</span>')
            facultatif = " (facultatif)" if e["facultatif"] else ""
            liens = '<a href="ecran:' + e["ecran"] + '">Ouvrir l\'écran</a>'
            if e.get("article"):
                liens += ' - <a href="guide:' + e["article"] + '">Comment faire</a>'
            lignes.append(
                '<tr><td width="28" valign="top">' + marque + "</td><td><b>"
                + escape(e["titre"]) + "</b>" + facultatif + "<br>" + escape(e["detail"])
                + "<br>" + liens + "</td></tr>")
        return (_style(couleur) + "<h2>Pour bien démarrer</h2>"
                + f"<p>{faites} étape(s) sur {len(obligatoires)} terminée(s). "
                "Chaque étape se coche toute seule quand elle est faite.</p>"
                + '<table cellpadding="6">' + "".join(lignes) + "</table>")

    def document(self, articles: list[Article], nom_ecole: str, couleur: str) -> str:
        """Guide complet, prêt à imprimer (une rubrique par page)."""
        morceaux = [_style(couleur),
                    f"<h1>Guide d'utilisation - {escape(nom_ecole or 'EduPaie')}</h1>",
                    "<p>Table des matières</p><ol>"]
        morceaux += [f"<li>{escape(a.titre)}</li>" for a in articles]
        morceaux.append("</ol>")
        for i, a in enumerate(articles, start=1):
            morceaux.append(f'<h2 style="page-break-before: always">{i}. '
                            f"{escape(a.titre)}</h2>" + self._rendre(a.corps))
        return "".join(morceaux)