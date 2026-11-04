"""Construit EduPaie : le dossier dist/EduPaie, puis l'installateur.
    python -m outils.construire             version de livraison (sans console)
    python -m outils.construire --console   version d'essai (erreurs visibles)"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from edupaie.version import VERSION

RACINE = Path(__file__).resolve().parent.parent
LOCAL = os.environ.get("LOCALAPPDATA", "")
CANDIDATS_ISCC = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    LOCAL + r"\Programs\Inno Setup 6\ISCC.exe",
]


def trouver_iscc():
    chemin = shutil.which("ISCC")
    if chemin:
        return chemin
    return next((c for c in CANDIDATS_ISCC if Path(c).exists()), None)


def main() -> int:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--console", action="store_true",
                         help="garde une fenêtre console (pour les essais)")
    options = parseur.parse_args()

    print(f"== PyInstaller : EduPaie {VERSION} ==")
    env = dict(os.environ, EDUPAIE_CONSOLE="1" if options.console else "0")
    pyinstaller = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "EduPaie.spec"]
    if subprocess.run(pyinstaller, cwd=RACINE, env=env).returncode:
        print("Échec de PyInstaller : lis le message ci-dessus.")
        return 1

    iscc = trouver_iscc()
    if not iscc:
        print("Inno Setup est introuvable : installe Inno Setup 6 (jrsoftware.org).")
        return 1
    script = RACINE / "installateur.iss"
    # Inno Setup lit les accents correctement seulement si le fichier est en UTF-8 avec BOM.
    script.write_text(script.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")

    print("== Inno Setup ==")
    if subprocess.run([iscc, f"/DAppVersion={VERSION}", str(script)], cwd=RACINE).returncode:
        print("Échec d'Inno Setup : lis le message ci-dessus.")
        return 1
    print("\nInstallateur prêt :", RACINE / "installateur" / f"EduPaie_Setup_{VERSION}.exe")
    return 0


if __name__ == "__main__":
    sys.exit(main())