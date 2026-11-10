"""Rôles et permissions d'EduPaie (alignés sur la contrainte CHECK de schema.sql)."""

ADMIN = "admin"
COMPTABLE = "comptable"
LECTURE = "lecture"

PERMISSIONS = {
    ADMIN: {
        "eleve.lire", "eleve.ecrire", "eleve.supprimer", "eleve.importer",
        "paiement.lire", "paiement.encaisser", "paiement.annuler",
        "recu.imprimer", "dashboard.voir",
        "utilisateur.gerer", "frais.gerer", "sauvegarde.gerer",
        "caisse.voir", "caisse.toutes", "remise.gerer", "impayes.voir",
        "ecole.gerer", "classe.gerer", "audit.voir", "annee.gerer", "licence.gerer",
        "recouvrement.voir",  "rapprochement.gerer",  "impayes.relancer",
    },
    COMPTABLE: {
        "eleve.lire", "eleve.ecrire",
        "paiement.lire", "paiement.encaisser",
        "recu.imprimer", "dashboard.voir",
        "caisse.voir", "impayes.voir", "impayes.relancer",
    },
    LECTURE: {
        "eleve.lire", "paiement.lire", "dashboard.voir",
    },
}

# Permissions conservées quand la licence est expirée (mode consultation)
SANS_LICENCE = {
    "eleve.lire", "paiement.lire", "dashboard.voir", "caisse.voir", "impayes.voir",
    "audit.voir", "sauvegarde.gerer", "licence.gerer", "recouvrement.voir",
}

ROLES = tuple(PERMISSIONS)


def a_permission(role: str, permission: str) -> bool:
    """True si le rôle donné possède la permission demandée."""
    return permission in PERMISSIONS.get(role, set())