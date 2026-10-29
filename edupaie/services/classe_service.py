import re

from edupaie.services.paiement_service import ErreurMetier

NOM_MAX = 30


class ClasseService:
    def __init__(self, repo, auth=None):
        self.repo = repo
        self.auth = auth  # None dans les tests : pas de contrôle de droits

    def _exiger(self):
        if self.auth is not None and not self.auth.peut("classe.gerer"):
            raise ErreurMetier("Seul un administrateur peut gérer les classes.")

    @staticmethod
    def _nom(texte) -> str:
        nom = " ".join(str(texte or "").split())
        if not nom:
            raise ErreurMetier("Le nom de la classe est obligatoire.")
        if len(nom) > NOM_MAX:
            raise ErreurMetier(f"« {nom[:20]}... » : {NOM_MAX} caractères au maximum.")
        return nom

    def _trouver(self, nom):
        cle = str(nom or "").casefold()
        courant = next((n for n in self.repo.noms() if n.casefold() == cle), None)
        if courant is None:
            raise ErreurMetier("Classe introuvable.")
        return courant

    def noms(self) -> list[str]:
        return self.repo.noms()

    def lister(self) -> list[dict]:
        utilisation = self.repo.utilisation()
        lignes = []
        for nom in self.repo.noms():
            eleves, frais, tranches = utilisation.get(nom.casefold(), (0, 0, 0))
            lignes.append({"nom": nom, "eleves": eleves, "frais": frais,
                           "tranches": tranches,
                           "supprimable": not (eleves or frais or tranches)})
        return lignes

    @staticmethod
    def serie(prefixe, sections) -> list[str]:
        """« 6e » + « A B C D » -> 6e A, 6e B, 6e C, 6e D."""
        prefixe = " ".join(str(prefixe or "").split())
        if not prefixe:
            raise ErreurMetier("Indique le niveau (par exemple 6e).")
        morceaux = [s for s in re.split(r"[\s,;]+", str(sections or "")) if s]
        return [f"{prefixe} {s}" for s in morceaux] if morceaux else [prefixe]

    def ajouter(self, nom) -> str:
        self._exiger()
        nom = self._nom(nom)
        if nom.casefold() in {n.casefold() for n in self.repo.noms()}:
            raise ErreurMetier(f"La classe « {nom} » existe déjà.")
        self.repo.ajouter(nom)
        return nom

    def ajouter_plusieurs(self, noms) -> tuple[int, int]:
        """Retourne (ajoutées, ignorées parce qu'elles existent déjà)."""
        self._exiger()
        valides = [self._nom(n) for n in noms if str(n or "").strip()]  # une erreur annule tout
        existants = {n.casefold() for n in self.repo.noms()}
        ajoutees = ignorees = 0
        for nom in valides:
            if nom.casefold() in existants:
                ignorees += 1
                continue
            self.repo.ajouter(nom)
            existants.add(nom.casefold())
            ajoutees += 1
        return ajoutees, ignorees

    def renommer(self, ancien, nouveau) -> None:
        self._exiger()
        nouveau = self._nom(nouveau)
        courant = self._trouver(ancien)
        if any(n.casefold() == nouveau.casefold() and n.casefold() != courant.casefold()
               for n in self.repo.noms()):
            raise ErreurMetier(f"La classe « {nouveau} » existe déjà.")
        if nouveau != courant:
            self.repo.renommer(courant, nouveau)

    def supprimer(self, nom) -> None:
        self._exiger()
        courant = self._trouver(nom)
        eleves, frais, tranches = self.repo.utilisation().get(courant.casefold(), (0, 0, 0))
        if eleves or frais or tranches:
            utilise = []
            if eleves:
                utilise.append(f"{eleves} élève(s)")
            if frais:
                utilise.append(f"{frais} ligne(s) de frais")
            if tranches:
                utilise.append(f"{tranches} tranche(s) d'échéancier")
            raise ErreurMetier(f"Impossible de supprimer « {courant} » : elle est encore "
                               f"utilisée par {', '.join(utilise)}.")
        self.repo.supprimer(courant)

    def deplacer(self, nom, delta: int) -> bool:
        self._exiger()
        return self.repo.deplacer(self._trouver(nom), delta)