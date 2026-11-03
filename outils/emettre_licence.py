"""Émet une clé de licence pour une école : python -m outils.emettre_licence"""
import re
import sys
from datetime import date
from pathlib import Path

from outils.licences import charger_cle_privee, emettre, enregistrer, prochain_numero

DOSSIER = Path(__file__).parent
CHEMIN_PRIVEE = DOSSIER / "cle_privee.pem"
REGISTRE = DOSSIER / "registre_licences.csv"
SORTIE = DOSSIER / "licences_emises"


def demander_date():
    while True:
        texte = input("Valable jusqu'au (AAAA-MM-JJ), vide = sans limite de durée : ").strip()
        if not texte:
            return None
        try:
            return date.fromisoformat(texte)
        except ValueError:
            print("Date invalide, exemple : 2027-10-31")


def main() -> int:
    if not CHEMIN_PRIVEE.exists():
        print("Clé privée introuvable : lance d'abord  python -m outils.generer_cles")
        return 1
    ecole = input("Nom de l'école : ").strip()
    machine = input("Identifiant de l'ordinateur (écran Licence d'EduPaie) ou * : ").strip()
    expire = demander_date()
    numero = prochain_numero(REGISTRE)
    try:
        cle = emettre(charger_cle_privee(CHEMIN_PRIVEE.read_bytes()),
                      ecole, machine, expire, numero)
    except ValueError as e:
        print("Licence refusée :", e)
        return 1
    enregistrer(REGISTRE, numero, ecole, machine.strip().upper(), expire)
    SORTIE.mkdir(exist_ok=True)
    fichier = SORTIE / f"{numero}_{re.sub(r'[^A-Za-z0-9]+', '_', ecole)[:40]}.licence"
    fichier.write_text(cle + "\n", encoding="utf-8")
    print(f"\nLicence {numero} émise pour « {ecole} ».")
    print("Fichier à envoyer :", fichier)
    print("\nOu la clé à copier-coller :\n")
    print(cle)
    return 0


if __name__ == "__main__":
    sys.exit(main())