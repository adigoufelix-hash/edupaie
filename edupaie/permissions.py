"""Rôles et permissions d'EduPaie (alignés sur la contrainte CHECK de schema.sql)."""

ADMIN = "admin"
COMPTABLE = "comptable"
LECTURE = "lecture"

PERMISSIONS = {
    ADMIN: {
        "eleve.lire", "eleve.ecrire", "eleve.supprimer",
        "paiement.lire", "paiement.encaisser",
        "recu.imprimer", "dashboard.voir",
        "utilisateur.gerer", "frais.gerer",
    },
    COMPTABLE: {
        "eleve.lire", "eleve.ecrire",
        "paiement.lire", "paiement.encaisser",
        "recu.imprimer", "dashboard.voir",
    },
    LECTURE: {
        "eleve.lire", "paiement.lire", "dashboard.voir",
    },
}

ROLES = tuple(PERMISSIONS)


def a_permission(role: str, permission: str) -> bool:
    """True si le rôle donné possède la permission demandée."""
    return permission in PERMISSIONS.get(role, set())