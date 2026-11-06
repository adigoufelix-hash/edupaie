import csv
import io
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from edupaie.services.paiement_service import ErreurMetier

TAILLE_MAX = 10_000_000
LIGNES_MAX = 20000

# Mots que l'on cherche dans les titres de colonnes, par ordre de préférence
SYNONYMES = {
    "date": ("date", "jour", "heure"),
    "montant": ("credit", "montant", "amount", "somme", "valeur"),
    "reference": ("reference", "transaction", "txn", "id"),
    "libelle": ("expediteur", "emetteur", "nom", "from", "telephone", "tel", "msisdn",
                "libelle", "description", "detail", "motif", "numero"),
    "sens": ("type", "sens", "operation", "nature"),
}


def cle(texte) -> str:
    """Forme comparable : sans accents, sans majuscules, sans ponctuation."""
    texte = unicodedata.normalize("NFD", str(texte or "").casefold())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


def _correspond(synonyme, mots) -> bool:
    return any(m == synonyme or (len(synonyme) >= 4 and m.startswith(synonyme)) for m in mots)


def lire_tableau(chemin) -> list[list]:
    """Lit un relevé Excel (.xlsx) ou CSV et retourne ses lignes brutes."""
    chemin = Path(chemin)
    if chemin.stat().st_size > TAILLE_MAX:
        raise ErreurMetier("Fichier trop volumineux (10 Mo au maximum).")
    extension = chemin.suffix.lower()
    if extension in (".xlsx", ".xlsm"):
        classeur = load_workbook(chemin, read_only=True, data_only=True)
        try:
            return [list(ligne) for _, ligne in
                    zip(range(LIGNES_MAX), classeur.active.iter_rows(values_only=True))]
        finally:
            classeur.close()
    if extension in (".csv", ".txt"):
        brut = chemin.read_bytes()
        texte = ""
        for encodage in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texte = brut.decode(encodage)
                break
            except UnicodeDecodeError:
                continue
        echantillon = "\n".join([l for l in texte.splitlines() if l.strip()][:10])
        separateur = max(";,\t|", key=echantillon.count)
        return [ligne for _, ligne in
                zip(range(LIGNES_MAX), csv.reader(io.StringIO(texte), delimiter=separateur))]
    raise ErreurMetier("Format non pris en charge : enregistre le relevé en Excel (.xlsx) "
                       "ou en CSV.")


def trouver_entete(lignes) -> int:
    """Index de la ligne des titres (les relevés ont souvent un en-tête avant)."""
    for i, brut in enumerate(lignes[:25]):
        mots = [cle(c).split() for c in brut
                if c is not None and not isinstance(c, (int, float, datetime, date))]
        a_date = any(_correspond("date", m) for m in mots)
        a_montant = any(_correspond(s, m) for s in SYNONYMES["montant"] for m in mots)
        if a_date and a_montant:
            return i
    return 0


def detecter_colonnes(entetes) -> dict:
    """{'date': 0, 'montant': 5, ...} ; None quand la colonne n'est pas trouvée."""
    mots = [cle(e).split() for e in entetes]
    trouve, utilisees = {}, set()
    for champ, synonymes in SYNONYMES.items():
        trouve[champ] = None
        for synonyme in synonymes:
            colonne = next((i for i, m in enumerate(mots)
                            if i not in utilisees and _correspond(synonyme, m)), None)
            if colonne is not None:
                trouve[champ] = colonne
                utilisees.add(colonne)
                break
    return trouve


def lire_montant(valeur):
    """Montant entier en FCFA (None si illisible ; peut être négatif)."""
    if valeur is None or isinstance(valeur, bool):
        return None
    unite = Decimal("1")
    if isinstance(valeur, (int, float, Decimal)):
        return int(Decimal(str(valeur)).quantize(unite, rounding=ROUND_HALF_UP))
    texte = re.sub(r"\s*(FCFA|XOF|CFA|F)\.?$", "", str(valeur).strip().upper())
    texte = texte.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    if not re.fullmatch(r"[-+]?[\d.,]+", texte):
        return None
    signe = -1 if texte.startswith("-") else 1
    texte = texte.lstrip("+-")
    if "," in texte and "." in texte:  # le dernier séparateur est la décimale
        decimale = "," if texte.rfind(",") > texte.rfind(".") else "."
        autre = "." if decimale == "," else ","
        texte = texte.replace(autre, "").replace(decimale, ".")
    elif "," in texte or "." in texte:
        separateur = "," if "," in texte else "."
        morceaux = texte.split(separateur)
        if len(morceaux) > 2 or len(morceaux[-1]) == 3:
            texte = "".join(morceaux)  # séparateur de milliers : 25.000 = 25 000 FCFA
        else:
            texte = ".".join(morceaux)
    try:
        return signe * int(Decimal(texte).quantize(unite, rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None


def lire_date(valeur):
    """Date au format AAAA-MM-JJ (jour d'abord pour les dates écrites 02/11/2026)."""
    if isinstance(valeur, datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        if 20000 < valeur < 80000:  # date Excel enregistrée comme un simple nombre
            return (date(1899, 12, 30) + timedelta(days=int(valeur))).isoformat()
        return None
    texte = str(valeur or "").strip()
    if not texte:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", texte)
    if m:
        annee, mois, jour = (int(x) for x in m.groups())
    else:
        m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", texte)
        if not m:
            return None
        jour, mois, annee = (int(x) for x in m.groups())
        if annee < 100:
            annee += 2000
    try:
        return date(annee, mois, jour).isoformat()
    except ValueError:
        return None


def _propre(valeur, maximum=80):
    if valeur is None:
        return None
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    texte = " ".join(str(valeur).split())[:maximum]
    return texte or None


def normaliser(lignes, colonnes, premiere=1, filtre=""):
    """Retourne (opérations valides, lignes écartées avec la raison).
    colonnes : {'date': i, 'montant': i, 'reference': i ou None, 'libelle': ..., 'sens': ...}
    filtre : ne garde que les lignes dont le type contient ce texte (ex. « crédit »)."""
    valides, ecartees = [], []
    filtre = cle(filtre)
    for numero, brut in enumerate(lignes[premiere:], start=premiere + 1):
        if not any(str(c if c is not None else "").strip() for c in brut):
            continue  # ligne vide

        def cellule(nom, brut=brut):
            i = colonnes.get(nom)
            return brut[i] if i is not None and i < len(brut) else None

        if filtre and filtre not in cle(cellule("sens")):
            ecartees.append((numero, "type d'opération ignoré"))
            continue
        jour = lire_date(cellule("date"))
        if jour is None:
            ecartees.append((numero, "date illisible"))
            continue
        montant = lire_montant(cellule("montant"))
        if montant is None or montant <= 0:
            ecartees.append((numero, "montant absent, nul ou négatif"))
            continue
        valides.append({"date": jour, "montant": montant,
                        "reference": _propre(cellule("reference")),
                        "libelle": _propre(cellule("libelle"))})
    return valides, ecartees