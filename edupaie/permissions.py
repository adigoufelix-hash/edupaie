"""Rôles et permissions d'EduPaie."""

ADMIN = "admin"
CAISSIER = "caissier"
CONSULTANT = "consultant"

PERMISSIONS = {
    ADMIN: {
        "eleve.lire", "eleve.ecrire", "eleve.supprimer",
        "paiement.lire", "paiement.encaisser",
        "recu.imprimer", "dashboard.voir", "utilisateur.gerer",
    },
    CAISSIER: {
        "eleve.lire", "eleve.ecrire",
        "paiement.lire", "paiement.encaisser",
        "recu.imprimer", "dashboard.voir",
    },
    CONSULTANT: {
        "eleve.lire", "paiement.lire", "dashboard.voir",
    },
}

ROLES = tuple(PERMISSIONS)


def a_permission(role: str, permission: str) -> bool:
    """True si le rôle donné possède la permission demandée."""
    return permission in PERMISSIONS.get(role, set())