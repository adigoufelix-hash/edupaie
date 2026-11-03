"""Remet à zéro la période d'essai et la licence sur CET ordinateur (tests du fournisseur)."""
import sqlite3
import sys
from pathlib import Path

from edupaie.db.connection import DB_PATH


def main() -> int:
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\EduPaie")
        print("Marques du registre supprimées.")
    except ImportError:
        fichier = Path.home() / ".edupaie_marques.json"
        if fichier.exists():
            fichier.unlink()
            print("Fichier de marques supprimé.")
    except OSError:
        print("Aucune marque dans le registre.")
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM parametre WHERE cle IN "
                     "('essai_debut', 'derniere_date', 'licence', 'licence_activee_le')")
        conn.commit()
        conn.close()
        print("Essai et licence remis à zéro dans la base.")
    return 0


if __name__ == "__main__":
    sys.exit(main())