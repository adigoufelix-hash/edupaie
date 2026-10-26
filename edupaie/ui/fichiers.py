import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

TABLEURS = ("excel.exe", "soffice.exe")  # noms enregistrés par Windows (« App Paths »)


def _chemin_enregistre(nom_exe):
    """Chemin d'un programme tel qu'enregistré par Windows, ou None."""
    import winreg
    cle_app = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{nom_exe}"
    for racine in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for vue in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(racine, cle_app, 0, winreg.KEY_READ | vue) as cle:
                    valeur = winreg.QueryValueEx(cle, "")[0].strip('"')
            except OSError:
                continue
            if valeur and Path(valeur).is_file():
                return valeur
    return None


def trouver_tableur():
    """Chemin de Excel ou de LibreOffice s'ils sont installés, sinon None."""
    if sys.platform != "win32":
        return None
    for nom in TABLEURS:
        chemin = _chemin_enregistre(nom)
        if chemin:
            return chemin
    for base in ("ProgramFiles", "ProgramFiles(x86)"):
        racine = os.environ.get(base)
        if not racine:
            continue
        for version in ("Office16", "Office15", "Office14"):
            excel = Path(racine) / "Microsoft Office" / version / "EXCEL.EXE"
            if excel.is_file():
                return str(excel)


def ouvrir_dans_un_tableur(chemin) -> bool:
    programme = trouver_tableur()
    if programme is None:
        return False
    try:
        subprocess.Popen([programme, str(chemin)])
    except OSError:
        return False
    return True


def _afficher_dans_le_dossier(chemin: Path):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{chemin}"])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin.parent)))


def apres_export(parent, chemin, titre="Export terminé"):
    """Ouvre le fichier exporté. Les .xlsx s'ouvrent directement dans Excel ou LibreOffice."""
    chemin = Path(chemin).resolve()
    if chemin.suffix.lower() not in (".xlsx", ".xls"):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin)))
        return
    if ouvrir_dans_un_tableur(chemin):
        return
    boite = QMessageBox(parent)
    boite.setWindowTitle(titre)
    boite.setText(
        "Excel ou LibreOffice n'a pas été trouvé sur cet ordinateur.\n\n"
        f"Le fichier est enregistré ici :\n{chemin}\n\n"
        "Ouvre-le avec ton tableur, ou installe LibreOffice (gratuit).")
    dossier = boite.addButton("Afficher dans le dossier", QMessageBox.ActionRole)
    boite.addButton("Fermer", QMessageBox.RejectRole)
    boite.exec()
    if boite.clickedButton() is dossier:
        _afficher_dans_le_dossier(chemin)