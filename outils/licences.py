"""Outils du fournisseur : à ne JAMAIS livrer aux écoles.
La clé privée ne doit jamais être dans Git ni dans un installateur."""
import csv
import json
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from edupaie.services.licence import MACHINE_VALIDE, construire_cle, normaliser_machine

ENTETES = ["numero", "ecole", "machine", "emise", "expire"]


def generer_paire():
    """Retourne (clé privée au format PEM, clé publique en hexadécimal)."""
    cle = Ed25519PrivateKey.generate()
    pem = cle.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption())
    publique = cle.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw).hex()
    return pem, publique


def charger_cle_privee(pem: bytes):
    return serialization.load_pem_private_key(pem, password=None)


def emettre(cle_privee, ecole, machine, expire, numero, emise=None) -> str:
    """Retourne la clé de licence (texte à envoyer à l'école)."""
    ecole = " ".join(str(ecole).split())
    if not ecole:
        raise ValueError("Le nom de l'école est obligatoire.")
    machine = normaliser_machine(machine)
    if machine != "*" and not MACHINE_VALIDE.fullmatch(machine):
        raise ValueError(
            "Identifiant d'ordinateur invalide (exemple : 3F2A-91BC-07DE-44A1).")
    donnees = {"v": 1, "id": numero, "ecole": ecole, "machine": machine,
               "emise": (emise or date.today()).isoformat(),
               "expire": expire.isoformat() if expire else None}
    brut = json.dumps(donnees, separators=(",", ":"), sort_keys=True,
                      ensure_ascii=False).encode("utf-8")
    return construire_cle(brut, cle_privee.sign(brut))


def prochain_numero(registre) -> str:
    registre = Path(registre)
    if not registre.exists():
        return "LIC-0001"
    with registre.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    dernier = max((int(l["numero"][4:]) for l in lignes
                   if l["numero"].startswith("LIC-")), default=0)
    return f"LIC-{dernier + 1:04d}"


def enregistrer(registre, numero, ecole, machine, expire, emise=None) -> None:
    """Ajoute la licence au registre de tes ventes (fichier CSV, ouvrable dans Excel)."""
    registre = Path(registre)
    nouveau = not registre.exists()
    with registre.open("a", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f, delimiter=";")
        if nouveau:
            ecrivain.writerow(ENTETES)
        ecrivain.writerow([numero, ecole, machine, (emise or date.today()).isoformat(),
                           expire.isoformat() if expire else "sans limite"])