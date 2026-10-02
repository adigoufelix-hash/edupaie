import shutil
import sqlite3
import sys
from pathlib import Path


def _dossier_application() -> Path:
    """Dossier de l'.exe une fois empaqueté, racine du projet sinon."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


DB_PATH = _dossier_application() / "data" / "edupaie.db"


def _preparer_base() -> None:
    """Au premier lancement de l'.exe, copie la base initiale embarquée."""
    if DB_PATH.exists() or not getattr(sys, "frozen", False):
        return
    modele = Path(sys._MEIPASS) / "data" / "edupaie.db"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(modele, DB_PATH)


def get_connection():
    _preparer_base()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn