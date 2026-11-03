"""Crée la paire de clés qui signe les licences. À lancer UNE SEULE FOIS."""
import sys
from pathlib import Path

from outils.licences import generer_paire

CHEMIN_PRIVEE = Path(__file__).with_name("cle_privee.pem")


def main() -> int:
    if CHEMIN_PRIVEE.exists():
        print("Une clé privée existe déjà :", CHEMIN_PRIVEE)
        print("Ne la remplace jamais : toutes les licences déjà émises deviendraient "
              "invalides.")
        return 1
    pem, publique = generer_paire()
    CHEMIN_PRIVEE.write_bytes(pem)
    print("Clé privée enregistrée :", CHEMIN_PRIVEE)
    print("  -> SAUVEGARDE-LA hors de l'ordinateur (clé USB, gestionnaire de mots de passe).")
    print("  -> Si tu la perds, tu ne pourras plus émettre de licences.")
    print("  -> Ne la mets JAMAIS dans Git ni dans un installateur.\n")
    print("Clé publique à coller dans edupaie/services/licence.py :\n")
    print(f'CLE_PUBLIQUE_HEX = "{publique}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())