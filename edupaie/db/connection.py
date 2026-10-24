import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path


def dossier_donnees() -> Path:
    """Dossier modifiable : AppData une fois installé, racine du projet sinon."""
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EduPaie"
    return Path(__file__).resolve().parent.parent.parent


def _chemin_schema() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data" / "schema.sql"
    return Path(__file__).resolve().parent.parent.parent / "data" / "schema.sql"


DB_PATH = dossier_donnees() / "data" / "edupaie.db"

# Colonnes ajoutées après la première version : ajoutées aux bases existantes.
COLONNES_PAIEMENT = {
    "utilisateur_id": "INTEGER REFERENCES utilisateur(id) ON DELETE SET NULL",
    "encaisse_par": "TEXT",
    "annule": "INTEGER NOT NULL DEFAULT 0",
    "motif_annulation": "TEXT",
    "annule_par": "TEXT",
    "annule_le": "TEXT",
}


def _migrer(conn: sqlite3.Connection) -> None:
    existantes = {r[1] for r in conn.execute("PRAGMA table_info(paiement)")}
    for nom, definition in COLONNES_PAIEMENT.items():
        if nom not in existantes:
            conn.execute(f"ALTER TABLE paiement ADD COLUMN {nom} {definition}")
    conn.commit()


def initialiser_base() -> None:
    """Crée la base si besoin, ajoute les tables et colonnes manquantes."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(_chemin_schema().read_text(encoding="utf-8"))
        _migrer(conn)
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()