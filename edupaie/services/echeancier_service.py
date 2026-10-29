import sqlite3
from datetime import date, datetime
from urllib.parse import quote

from edupaie.services.paiement_service import ErreurMetier

INDICATIF_PAYS = "228"  # Togo


def normaliser_telephone(texte, indicatif=INDICATIF_PAYS):
    """Numéro au format international (chiffres seulement), ou None s'il est invalide."""
    chiffres = "".join(c for c in str(texte) if c.isdigit())
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    elif len(chiffres) == 8:  # numéro local
        chiffres = indicatif + chiffres
    return chiffres if 10 <= len(chiffres) <= 15 else None


def _montant(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ") + " FCFA"


def _date_fr(iso: str) -> str:
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}/{annee}"


class EcheancierService:
    def __init__(self, echeance_repo, eleve_repo, paiement_repo, contact_repo, auth=None):
        self.echeances = echeance_repo
        self.eleves = eleve_repo
        self.paiements = paiement_repo
        self.contacts = contact_repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits

    # --- Droits ------------------------------------------------------------------
    def _exiger(self, permission: str, message: str):
        if self.auth is not None and not self.auth.peut(permission):
            raise ErreurMetier(message)

    def _exiger_admin(self):
        self._exiger("frais.gerer", "Action réservée à l'administrateur.")

    def peut_modifier_contact(self) -> bool:
        return self.auth is None or self.auth.peut("eleve.ecrire")

    # --- Validation ----------------------------------------------------------------
    @staticmethod
    def _valider_classe(classe, annee):
        classe, annee = str(classe).strip(), str(annee).strip()
        if not classe:
            raise ErreurMetier("La classe est obligatoire.")
        if not annee:
            raise ErreurMetier("L'année scolaire est obligatoire.")
        return classe, annee

    @staticmethod
    def _valider_date(valeur) -> str:
        try:
            return datetime.strptime(str(valeur).strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ErreurMetier("Date invalide (format attendu : AAAA-MM-JJ).") from None

    @classmethod
    def _valider_ligne(cls, libelle, date_limite, pourcentage):
        libelle = str(libelle).strip()
        if not libelle:
            raise ErreurMetier("Le nom de la tranche est obligatoire.")
        date_limite = cls._valider_date(date_limite)
        try:
            pct = int("".join(str(pourcentage).replace("%", " ").split()))
        except ValueError:
            raise ErreurMetier("Le pourcentage doit être un nombre entier.") from None
        if not 1 <= pct <= 100:
            raise ErreurMetier("Le pourcentage doit être compris entre 1 et 100.")
        return libelle, date_limite, pct

    # --- Tranches -----------------------------------------------------------------
    def classes(self) -> list[str]:
        return self.echeances.classes()
    def lister(self, classe: str, annee: str):
        return self.echeances.lister(classe.strip(), annee.strip())

    def total_pourcentage(self, classe: str, annee: str) -> int:
        return self.echeances.total_pourcentage(classe.strip(), annee.strip())

    def ajouter_ligne(self, classe, annee, libelle, date_limite, pourcentage) -> int:
        self._exiger_admin()
        classe, annee = self._valider_classe(classe, annee)
        libelle, date_limite, pct = self._valider_ligne(libelle, date_limite, pourcentage)
        deja = self.echeances.total_pourcentage(classe, annee)
        if deja + pct > 100:
            raise ErreurMetier(
                f"Le total des tranches dépasserait 100 % (déjà {deja} %).")
        try:
            return self.echeances.ajouter(classe, annee, libelle, date_limite, pct)
        except sqlite3.IntegrityError:
            raise ErreurMetier("Une tranche porte déjà ce nom pour cette classe.") from None

    def modifier_ligne(self, echeance_id, libelle, date_limite, pourcentage) -> None:
        self._exiger_admin()
        ligne = self.echeances.obtenir(echeance_id)
        if ligne is None:
            raise ErreurMetier("Tranche introuvable.")
        libelle, date_limite, pct = self._valider_ligne(libelle, date_limite, pourcentage)
        autres = self.echeances.total_pourcentage(
            ligne["classe"], ligne["annee_scolaire"], sauf_id=echeance_id)
        if autres + pct > 100:
            raise ErreurMetier(
                f"Le total des tranches dépasserait 100 % (autres tranches : {autres} %).")
        try:
            self.echeances.modifier(echeance_id, libelle, date_limite, pct)
        except sqlite3.IntegrityError:
            raise ErreurMetier("Une autre tranche porte déjà ce nom.") from None

    def supprimer_ligne(self, echeance_id: int) -> None:
        self._exiger_admin()
        self.echeances.supprimer(echeance_id)

    def copier(self, classe_source, annee, classe_cible) -> int:
        """Copie les tranches d'une classe vers une autre (sans écraser l'existant)."""
        self._exiger_admin()
        classe_source, annee = self._valider_classe(classe_source, annee)
        classe_cible, _ = self._valider_classe(classe_cible, annee)
        if classe_cible == classe_source:
            raise ErreurMetier("Choisis une autre classe que la classe d'origine.")
        lignes = self.echeances.lister(classe_source, annee)
        if not lignes:
            raise ErreurMetier("Cette classe n'a aucune tranche à copier.")
        deja = {l["libelle"].lower() for l in self.echeances.lister(classe_cible, annee)}
        a_copier = [l for l in lignes if l["libelle"].lower() not in deja]
        total = (self.echeances.total_pourcentage(classe_cible, annee)
                 + sum(l["pourcentage"] for l in a_copier))
        if total > 100:
            raise ErreurMetier("La copie ferait dépasser 100 % pour la classe cible.")
        for l in a_copier:
            self.echeances.ajouter(
                classe_cible, annee, l["libelle"], l["date_limite"], l["pourcentage"])
        return len(a_copier)

    # --- Impayés -------------------------------------------------------------------
    def impayes(self, date_ref=None, classe=None) -> dict:
        """Élèves en retard à la date donnée (aujourd'hui par défaut)."""
        self._exiger("impayes.voir", "Votre rôle ne permet pas de consulter les impayés.")
        ref = self._valider_date(date_ref) if date_ref else date.today().isoformat()
        ref_date = date.fromisoformat(ref)
        lignes, sans_echeancier = [], 0
        for eleve in self.eleves.lister("", classe):
            tranches = self.echeances.lister(eleve.classe, eleve.annee_scolaire)
            if not tranches:
                sans_echeancier += 1
                continue
            net = eleve.total_du - self.paiements.total_remises(eleve.id)
            paye = self.paiements.total_paye(eleve.id)
            cumul = exigible = 0
            premiere = None  # plus ancienne échéance non couverte par les paiements
            for t in tranches:  # triées par date limite
                if t["date_limite"] > ref:
                    break
                cumul += t["pourcentage"]
                exigible = net * cumul // 100
                if premiere is None and exigible > paye:
                    premiere = t
            retard = max(exigible - paye, 0)
            if retard <= 0:
                continue
            contact = self.contacts.get(eleve.id)
            lignes.append({
                "eleve_id": eleve.id,
                "nom": f"{eleve.nom} {eleve.prenom}",
                "classe": eleve.classe,
                "tranche": premiere["libelle"],
                "date_limite": premiere["date_limite"],
                "jours": (ref_date - date.fromisoformat(premiere["date_limite"])).days,
                "exigible": exigible, "paye": paye, "retard": retard,
                "tuteur": contact["tuteur"] if contact else "",
                "telephone": contact["telephone"] if contact else "",
            })
        lignes.sort(key=lambda l: (l["classe"], l["nom"]))
        return {"date_ref": ref, "lignes": lignes,
                "total_retard": sum(l["retard"] for l in lignes),
                "sans_echeancier": sans_echeancier}

    # --- Relance --------------------------------------------------------------------
    @staticmethod
    def message_relance(ligne) -> str:
        return (f"Bonjour, nous vous informons que l'élève {ligne['nom']} ({ligne['classe']}) "
                f"a un solde en retard de {_montant(ligne['retard'])} "
                f"(échéance « {ligne['tranche']} » du {_date_fr(ligne['date_limite'])}). "
                "Merci de passer régulariser à l'administration de l'école. Cordialement.")

    def lien_whatsapp(self, ligne):
        """Lien WhatsApp avec message prérempli, ou None si le numéro est invalide."""
        numero = normaliser_telephone(ligne.get("telephone") or "")
        if numero is None:
            return None
        return f"https://wa.me/{numero}?text={quote(self.message_relance(ligne))}"

    # --- Contact du parent ----------------------------------------------------------
    def contact(self, eleve_id: int):
        return self.contacts.get(eleve_id)

    def enregistrer_contact(self, eleve_id: int, tuteur, telephone) -> None:
        if not self.peut_modifier_contact():
            raise ErreurMetier("Votre rôle ne permet pas de modifier les contacts.")
        if self.eleves.get(eleve_id) is None:
            raise ErreurMetier("Élève introuvable.")
        tuteur = str(tuteur).strip()
        telephone = " ".join(str(telephone).split())
        if telephone and normaliser_telephone(telephone) is None:
            raise ErreurMetier(
                "Numéro invalide : 8 chiffres (Togo) ou numéro international avec "
                "indicatif, par exemple +233 24 123 4567.")
        self.contacts.enregistrer(eleve_id, tuteur, telephone)