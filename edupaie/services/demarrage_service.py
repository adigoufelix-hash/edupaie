from edupaie.services.ecole import courant


class DemarrageService:
    """Les étapes de mise en service d'une école, cochées d'après les vraies données."""

    def __init__(self, repo, auth, sauvegarde=None, licence=None, ecole=courant):
        self.repo = repo
        self.auth = auth
        self.sauvegarde = sauvegarde
        self.licence = licence
        self.ecole = ecole  # fonction sans argument qui retourne les paramètres de l'école

    def visible(self) -> bool:
        return self.auth is None or self.auth.peut("ecole.gerer")

    def etapes(self) -> list[dict]:
        nb_classes = len(self.repo.classes())
        nb_frais = self.repo.compter("frais_classe")
        nb_tranches = self.repo.compter("echeance")
        nb_eleves = self.repo.compter("eleve")
        nb_comptes = self.repo.compter("utilisateur")
        nb_admins = self.auth.nombre_admins() if self.auth is not None else 0
        codes = self.auth.codes_secours_restants() if self.auth is not None else 0
        sauvegardes = self.sauvegarde.lister() if self.sauvegarde is not None else []
        manuelle = any(s["motif"] == "manuelle" for s in sauvegardes)
        mode = self.licence.etat().mode if self.licence is not None else "licence"

        def etape(id_, titre, detail, fait, ecran, article, facultatif=False):
            return {"id": id_, "titre": titre, "detail": detail, "fait": bool(fait),
                    "facultatif": facultatif, "ecran": ecran, "article": article}

        return [
            etape("ecole", "Renseigner les informations de l'école",
                  "Nom, adresse, logo et couleur : ils apparaissent sur les reçus et les PDF.",
                  bool(self.ecole().nom), "parametres", "parametres"),
            etape("classes", "Créer les classes", f"{nb_classes} classe(s) enregistrée(s).",
                  nb_classes > 0, "classes", "classes"),
            etape("frais", "Définir les frais de chaque classe",
                  f"{nb_frais} ligne(s) de frais définie(s).", nb_frais > 0, "frais", "frais"),
            etape("echeancier", "Définir l'échéancier des classes",
                  f"{nb_tranches} tranche(s) définie(s). Nécessaire pour suivre les impayés.",
                  nb_tranches > 0, "frais", "frais", facultatif=True),
            etape("eleves", "Enregistrer les élèves",
                  f"{nb_eleves} élève(s) enregistré(s). Le plus rapide : importer un fichier "
                  "Excel.", nb_eleves > 0, "eleves", "import"),
            etape("comptes", "Créer les comptes du personnel",
                  f"{nb_comptes} compte(s) au total. Un compte par caissier.",
                  nb_comptes > 1, "utilisateurs", "utilisateurs"),
            etape("admin2", "Créer un second compte administrateur",
                  "Indispensable pour ne jamais perdre l'accès à l'application.",
                  nb_admins >= 2, "utilisateurs", "utilisateurs"),
            etape("codes", "Noter les codes de secours",
                  "Imprime la feuille et range-la dans un endroit sûr.",
                  codes > 0, "utilisateurs", "mot_de_passe"),
            etape("sauvegarde", "Faire une sauvegarde manuelle sur une clé USB",
                  "En plus des copies automatiques.", manuelle, "sauvegardes", "sauvegardes"),
            etape("licence", "Activer la licence",
                  "Licence active." if mode == "licence" else
                  "Période d'essai ou mode consultation : une licence est nécessaire.",
                  mode == "licence", "licence", "licence"),
        ]