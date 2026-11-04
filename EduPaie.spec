# -*- mode: python ; coding: utf-8 -*-
import os

# Console visible seulement pour les essais : EDUPAIE_CONSOLE=1 (voir outils/construire.py)
CONSOLE = os.environ.get("EDUPAIE_CONSOLE") == "1"

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('data/schema.sql', 'data'), ('assets/EduPaie.ico', 'assets')],
    hiddenimports=['fpdf', 'openpyxl', 'segno', 'cryptography'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['outils', 'tests', 'tkinter', 'pytest'],  # outils/ contient tes outils de licence
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # mode dossier : les fichiers sont dans COLLECT ci-dessous
    name='EduPaie',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX provoque de fausses alertes antivirus
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/EduPaie.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EduPaie',
)