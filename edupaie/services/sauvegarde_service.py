import sqlite3
from datetime import datetime
from pathlib import Path

from edupaie.db.connection import DB_PATH, dossier_donnees
from edupaie.services.paiement_service import ErreurMetier

TABLES_ATTENDUES = {"eleve", "paiement", "utilisateur"}


class SauvegardeService:
    def __init__(self, auth=None, chemin_base=DB_PATH, dossier=None, garder=30):
        self.auth = auth  # None : pas de contrôle de droits (tests)
        self.chemin_base = Path(chemin_base)
        self.dossier = Path(dossier) if dossier else dossier_donnees() / "sauvegardes"
        self.garder = garder

    def _exiger_droit(self):
        if self.auth is not None and not self.auth.peut("sauvegarde.gerer"):
            raise ErreurMetier("Action réservée à l'administrateur.")

    @staticmethod
    def _copier(source: Path, cible: Path) -> None:
        """Copie cohérente, même si la base est ouverte par l'application."""
        src = sqlite3.connect(source)
        dst = sqlite3.connect(cible)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

    def _creer(self, motif: str, dossier: Path | None = None) -> Path:
        if not self.chemin_base.exists():
            raise ErreurMetier("Base de données introuvable.")
        destination = Path(dossier) if dossier else self.dossier
        destination.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cible = destination / f"edupaie_{horodatage}_{motif}.db"
        self._copier(self.chemin_base, cible)
        if dossier is None:
            self._purger()
        return cible

    def _purger(self) -> None:
        fichiers = sorted(self.dossier.glob("edupaie_*.db"))
        for ancien in fichiers[:-self.garder]:
            ancien.unlink(missing_ok=True)

    def sauvegarder(self, motif: str = "manuelle", dossier: Path | None = None) -> Path:
        """Sauvegarde demandée par un administrateur (dossier : clé USB, etc.)."""
        self._exiger_droit()
        return self._creer(motif, dossier)

    def sauvegarde_auto(self) -> Path | None:
        """Au lancement et à la fermeture ; ne fait rien si rien n'a changé."""
        if not self.chemin_base.exists():
            return None
        existantes = list(self.dossier.glob("edupaie_*.db"))
        if existantes and max(f.stat().st_mtime for f in existantes) \
                >= self.chemin_base.stat().st_mtime:
            return None
        return self._creer("auto")

    def lister(self) -> list[dict]:
        resultat = []
        for f in sorted(self.dossier.glob("edupaie_*.db"), reverse=True):
            morceaux = f.stem.split("_")  # edupaie, date, heure, motif
            try:
                date = datetime.strptime(
                    f"{morceaux[1]} {morceaux[2]}", "%Y-%m-%d %H-%M-%S")
            except (IndexError, ValueError):
                date = datetime.fromtimestamp(f.stat().st_mtime)
            motif = "_".join(morceaux[3:]) if len(morceaux) > 3 else ""
            resultat.append({"chemin": f, "date": date,
                             "taille": f.stat().st_size, "motif": motif})
        return resultat

    @staticmethod
    def _verifier(chemin: Path) -> None:
        invalide = ErreurMetier("Ce fichier n'est pas une sauvegarde EduPaie valide.")
        if not chemin.is_file():
            raise ErreurMetier("Fichier de sauvegarde introuvable.")
        try:
            conn = sqlite3.connect(f"{chemin.resolve().as_uri()}?mode=ro", uri=True)
            try:
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'")}
                integrite = conn.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            raise invalide from None
        if integrite != "ok" or not TABLES_ATTENDUES <= tables:
            raise invalide

    def restaurer(self, chemin) -> None:
        """Remplace les données actuelles (une copie de sécurité est faite avant)."""
        self._exiger_droit()
        chemin = Path(chemin)
        self._verifier(chemin)
        if self.chemin_base.exists():
            self._creer("avant-restauration")
        self._copier(chemin, self.chemin_base)