import shutil
import sqlite3
import sys
from pathlib import Path

from contextlib import contextmanager


@contextmanager
def transaction():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


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

_SCHEMA_UTILISATEUR = """
CREATE TABLE IF NOT EXISTS utilisateur (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    login        TEXT NOT NULL UNIQUE,
    nom_complet  TEXT NOT NULL,
    mot_de_passe TEXT NOT NULL,   -- format : iterations$sel$hash (hex)
    role         TEXT NOT NULL CHECK (role IN ('admin', 'comptable', 'lecture')),
    actif        INTEGER NOT NULL DEFAULT 1,
    cree_le      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
_schema_pret = False


def get_connection():
    global _schema_pret
    _preparer_base()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not _schema_pret:
        conn.executescript(_SCHEMA_UTILISATEUR)
        _schema_pret = True
    return conn