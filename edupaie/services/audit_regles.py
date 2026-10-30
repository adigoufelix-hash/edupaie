from pathlib import Path

from edupaie.services.audit import Regle


def _texte(valeur) -> str:
    return " ".join(str(valeur).split()) if valeur is not None else ""


def _entier(valeur):
    try:
        return int("".join(str(valeur).split()))
    except (TypeError, ValueError):
        return None


def _fcfa(valeur) -> str:
    nombre = _entier(valeur)
    return f"{nombre:,}".replace(",", " ") + " FCFA" if nombre is not None else str(valeur)


def _nom_eleve(service, eleve_id) -> str:
    try:
        eleve = service.eleves.get(eleve_id)
    except Exception:
        eleve = None
    return f"{eleve.nom} {eleve.prenom}" if eleve else f"élève n°{eleve_id}"


def _premier(arguments):
    return next(iter(arguments.values()), None)


# --- Élèves ------------------------------------------------------------------------
def _eleve_existant(service, eleve_id):
    return next((e for e in service.lister() if e.id == eleve_id), None)


def regles_eleve():
    def avant_enregistrer(service, a):
        eleve_id = _premier(a)
        return None if eleve_id is None else _eleve_existant(service, eleve_id)

    def apres_enregistrer(service, a, resultat, avant):
        eleve_id, nom, prenom, classe, annee, total = list(a.values())[:6]
        if eleve_id is None:
            return {"action": "eleve.creation", "objet": "eleve",
                    "objet_id": resultat if isinstance(resultat, int) else None,
                    "detail": f"{_texte(nom)} {_texte(prenom)} ({_texte(classe)}, "
                              f"{_texte(annee)}) - total {_fcfa(total)}"}
        if avant is None:
            return {"action": "eleve.modification", "objet": "eleve",
                    "objet_id": eleve_id, "detail": f"Élève n°{eleve_id}"}
        changements = []
        for libelle, ancien, nouveau in (
                ("nom", avant.nom, nom), ("prénom", avant.prenom, prenom),
                ("classe", avant.classe, classe), ("année", avant.annee_scolaire, annee)):
            if _texte(ancien) != _texte(nouveau):
                changements.append(f"{libelle} : {_texte(ancien)} → {_texte(nouveau)}")
        if _entier(avant.total_du) != _entier(total):
            changements.append(f"total : {_fcfa(avant.total_du)} → {_fcfa(total)}")
        return {"action": "eleve.modification", "objet": "eleve", "objet_id": eleve_id,
                "detail": f"{avant.nom} {avant.prenom} : "
                          + ("; ".join(changements) or "aucun changement")}

    def avant_supprimer(service, a):
        return _eleve_existant(service, _premier(a))

    def apres_supprimer(service, a, resultat, avant):
        eleve_id = _premier(a)
        detail = (f"{avant.nom} {avant.prenom} ({avant.classe}, {avant.annee_scolaire})"
                  if avant else f"Élève n°{eleve_id}")
        return {"action": "eleve.suppression", "objet": "eleve",
                "objet_id": eleve_id, "detail": detail}

    return {"enregistrer": Regle(apres_enregistrer, avant_enregistrer),
            "supprimer": Regle(apres_supprimer, avant_supprimer)}


# --- Paiements -----------------------------------------------------------------------
def regles_paiement():
    def enregistrement(service, a, p, avant):
        return {"action": "paiement.enregistrement", "objet": "paiement", "objet_id": p.id,
                "detail": f"Reçu {p.numero_recu} - {_fcfa(p.montant)} ({p.mode}) - "
                          f"{_nom_eleve(service, p.eleve_id)}"}

    def annulation(service, a, p, avant):
        return {"action": "paiement.annulation", "objet": "paiement", "objet_id": p.id,
                "detail": f"Reçu {p.numero_recu} - {_fcfa(p.montant)} - "
                          f"{_nom_eleve(service, p.eleve_id)} - motif : "
                          f"{_texte(p.motif_annulation)}"}

    return {"enregistrer_paiement": Regle(enregistrement),
            "annuler_paiement": Regle(annulation)}


# --- Remises -------------------------------------------------------------------------
def regles_remise():
    def accordee(service, a, remise_id, avant):
        montant = (f"{_texte(a['valeur'])} %" if a["type_"] == "pourcentage"
                   else _fcfa(a["valeur"]))
        return {"action": "remise.accordee", "objet": "remise", "objet_id": remise_id,
                "detail": f"{_nom_eleve(service, a['eleve_id'])} : remise de {montant} - "
                          f"motif : {_texte(a['motif'])}"}

    def avant_annuler(service, a):
        return service.remises.obtenir(a["remise_id"])

    def annulee(service, a, resultat, avant):
        nom = _nom_eleve(service, avant["eleve_id"]) if avant else "?"
        montant = _fcfa(avant["montant"]) if avant else "?"
        return {"action": "remise.annulee", "objet": "remise", "objet_id": a["remise_id"],
                "detail": f"{nom} : remise de {montant} annulée - motif : "
                          f"{_texte(a['motif'])}"}

    return {"accorder": Regle(accordee), "annuler": Regle(annulee, avant_annuler)}


# --- Frais et échéancier ---------------------------------------------------------------
def regles_frais():
    def ajout(service, a, frais_id, avant):
        return {"action": "frais.ajout", "objet": "frais", "objet_id": frais_id,
                "detail": f"{a['classe']} ({a['annee']}) : {_texte(a['libelle'])} "
                          f"{_fcfa(a['montant'])}"}

    def modification(service, a, resultat, avant):
        return {"action": "frais.modification", "objet": "frais", "objet_id": a["frais_id"],
                "detail": f"Ligne n°{a['frais_id']} : {_texte(a['libelle'])} "
                          f"{_fcfa(a['montant'])}"}

    def avant_suppression(service, a):
        return service.repo.conn.execute(
            "SELECT classe, annee_scolaire, libelle, montant FROM frais_classe "
            "WHERE id = ?", (a["frais_id"],)).fetchone()

    def suppression(service, a, resultat, avant):
        detail = (f"{avant['classe']} ({avant['annee_scolaire']}) : {avant['libelle']} "
                  f"{_fcfa(avant['montant'])}" if avant else f"Ligne n°{a['frais_id']}")
        return {"action": "frais.suppression", "objet": "frais",
                "objet_id": a["frais_id"], "detail": detail}

    def copie(service, a, nombre, avant):
        return {"action": "frais.copie",
                "detail": f"{a['classe_source']} → {a['classe_cible']} ({a['annee']}) : "
                          f"{nombre} ligne(s)"}

    return {"ajouter_ligne": Regle(ajout), "modifier_ligne": Regle(modification),
            "supprimer_ligne": Regle(suppression, avant_suppression),
            "copier": Regle(copie)}


def regles_echeancier():
    def ajout(service, a, echeance_id, avant):
        return {"action": "echeancier.ajout", "objet": "echeance", "objet_id": echeance_id,
                "detail": f"{a['classe']} ({a['annee']}) : {_texte(a['libelle'])} - "
                          f"{_texte(a['pourcentage'])} % avant le {a['date_limite']}"}

    def modification(service, a, resultat, avant):
        return {"action": "echeancier.modification", "objet": "echeance",
                "objet_id": a["echeance_id"],
                "detail": f"Tranche n°{a['echeance_id']} : {_texte(a['libelle'])} - "
                          f"{_texte(a['pourcentage'])} % avant le {a['date_limite']}"}

    def avant_suppression(service, a):
        return service.echeances.obtenir(a["echeance_id"])

    def suppression(service, a, resultat, avant):
        detail = (f"{avant['classe']} ({avant['annee_scolaire']}) : {avant['libelle']}"
                  if avant else f"Tranche n°{a['echeance_id']}")
        return {"action": "echeancier.suppression", "objet": "echeance",
                "objet_id": a["echeance_id"], "detail": detail}

    def copie(service, a, nombre, avant):
        return {"action": "echeancier.copie",
                "detail": f"{a['classe_source']} → {a['classe_cible']} ({a['annee']}) : "
                          f"{nombre} tranche(s)"}

    def contact(service, a, resultat, avant):  # le numéro lui-même n'est pas journalisé
        return {"action": "contact.modification", "objet": "eleve",
                "objet_id": a["eleve_id"],
                "detail": f"Contact du parent mis à jour : "
                          f"{_nom_eleve(service, a['eleve_id'])}"}

    return {"ajouter_ligne": Regle(ajout), "modifier_ligne": Regle(modification),
            "supprimer_ligne": Regle(suppression, avant_suppression),
            "copier": Regle(copie), "enregistrer_contact": Regle(contact)}


# --- Comptes et connexions ---------------------------------------------------------------
def regles_auth():
    """Les mots de passe et les codes de secours ne sont jamais journalisés."""
    def creation(service, a, utilisateur_id, avant):
        ligne = service.repo.get(utilisateur_id)
        detail = f"{ligne['login']} ({ligne['role']})" if ligne else f"id {utilisateur_id}"
        return {"action": "utilisateur.creation", "objet": "utilisateur",
                "objet_id": utilisateur_id, "detail": detail}

    def avant_compte(service, a):
        return service.repo.get(a["utilisateur_id"])

    def suppression(service, a, resultat, avant):
        detail = f"{avant['login']} ({avant['role']})" if avant else f"id {a['utilisateur_id']}"
        return {"action": "utilisateur.suppression", "objet": "utilisateur",
                "objet_id": a["utilisateur_id"], "detail": detail}

    def reinitialisation(service, a, resultat, avant):
        detail = f"Compte {avant['login']}" if avant else f"id {a['utilisateur_id']}"
        return {"action": "utilisateur.mdp_reinitialise", "objet": "utilisateur",
                "objet_id": a["utilisateur_id"], "detail": detail}

    def changement(service, a, resultat, avant):
        return {"action": "utilisateur.mdp_change",
                "detail": "Mot de passe modifié par son titulaire"}

    def connexion(service, a, utilisateur, avant):
        if utilisateur:
            return {"action": "connexion", "objet": "utilisateur",
                    "objet_id": utilisateur["id"],
                    "detail": f"{utilisateur['login']} ({utilisateur['role']})"}
        return {"action": "echec_connexion", "acteur": (None, None),
                "detail": f"Identifiant saisi : {_texte(a['login'])[:40]}"}

    def blocage(service, a, exception):
        return {"action": "blocage_connexion", "acteur": (None, None),
                "detail": f"Tentative sur le compte « {_texte(a['login'])[:40]} » "
                          "alors qu'il est bloqué"}

    def codes(service, a, resultat, avant):
        return {"action": "utilisateur.codes_secours",
                "detail": "Nouveaux codes de secours générés (les anciens sont invalidés)"}

    def recuperation(service, a, restants, avant):
        return {"action": "utilisateur.recuperation", "acteur": (None, None),
                "detail": f"Compte {_texte(a['login'])[:40]} : mot de passe récupéré avec "
                          f"un code de secours ({restants} code(s) restant(s))"}

    def echec_recuperation(service, a, exception):
        return {"action": "utilisateur.recuperation_echec", "acteur": (None, None),
                "detail": f"Récupération sur « {_texte(a['login'])[:40]} » : {exception}"}

    return {"creer_utilisateur": Regle(creation),
            "supprimer_utilisateur": Regle(suppression, avant_compte),
            "reinitialiser_mot_de_passe": Regle(reinitialisation, avant_compte),
            "changer_mon_mot_de_passe": Regle(changement),
            "authentifier": Regle(connexion, None, blocage),
            "generer_codes_secours": Regle(codes),
            "reinitialiser_avec_code": Regle(recuperation, None, echec_recuperation)}

# --- Système ------------------------------------------------------------------------------
def regles_sauvegarde():
    def sauvegarde(service, a, resultat, avant):
        if a["motif"] != "manuelle":
            return None
        destination = f" vers {a['dossier']}" if a["dossier"] else ""
        return {"action": "sauvegarde.manuelle", "detail": f"Sauvegarde manuelle{destination}"}

    def restauration(service, a, resultat, avant):
        return {"action": "sauvegarde.restauration",
                "detail": f"Restauration de la sauvegarde {Path(str(a['chemin'])).name}"}

    return {"sauvegarder": Regle(sauvegarde), "restaurer": Regle(restauration)}


def regles_ecole():
    def modification(service, a, resultat, avant):
        return {"action": "ecole.modification",
                "detail": f"Paramètres de l'école mis à jour ({_texte(a['nom'])})"}

    return {"enregistrer": Regle(modification)}


def regles_import():
    def importation(service, a, nombre, avant):
        fichier = a["analyse"].get("fichier", "?") if isinstance(a["analyse"], dict) else "?"
        return {"action": "eleve.import",
                "detail": f"{nombre} élève(s) importé(s) depuis {fichier}"}

    return {"importer": Regle(importation)}


def regles_classe():
    def ajout(service, a, nom, avant):
        return {"action": "classe.ajout", "detail": f"Classe {nom}"}

    def ajout_lot(service, a, resultat, avant):
        ajoutees, ignorees = resultat
        return {"action": "classe.ajout",
                "detail": f"{ajoutees} classe(s) ajoutée(s), {ignorees} déjà existante(s)"}

    def renommage(service, a, resultat, avant):
        return {"action": "classe.renommage",
                "detail": f"{_texte(a['ancien'])} → {_texte(a['nouveau'])}"}

    def suppression(service, a, resultat, avant):
        return {"action": "classe.suppression", "detail": f"Classe {_texte(a['nom'])}"}

    return {"ajouter": Regle(ajout), "ajouter_plusieurs": Regle(ajout_lot),
            "renommer": Regle(renommage), "supprimer": Regle(suppression)}


def regles_verification():
    LIBELLES = {"falsifie": "reçu falsifié ou modifié", "introuvable": "reçu introuvable",
                "annule": "reçu annulé présenté"}

    def verification(service, a, resultat, avant):
        if resultat["statut"] not in LIBELLES:
            return None
        return {"action": "recu.alerte",
                "detail": f"{LIBELLES[resultat['statut']].capitalize()} - saisie : "
                          f"{_texte(a['saisie'])[:60]}"}

    return {"verifier": Regle(verification)}

def regles_annee():
    def passage(service, a, r, avant):
        return {"action": "annee.passage",
                "detail": f"Passage {a['annee_source']} → {r['cible']} : "
                          f"{r['reinscrits']} réinscrit(s), {r['sortants']} sortant(s), "
                          f"arriérés reportés : {_fcfa(r['arrieres'])}"}

    def active(service, a, resultat, avant):
        return {"action": "annee.active", "detail": f"Année active : {_texte(a['annee'])}"}

    def frais(service, a, r, avant):
        return {"action": "annee.frais",
                "detail": f"Frais et échéanciers repris de {a['annee_source']} vers "
                          f"{r['cible']} : {r['frais_lignes']} ligne(s) de frais, "
                          f"{r['echeance_lignes']} tranche(s)"}

    return {"executer": Regle(passage), "definir_active": Regle(active),
            "reprendre_frais": Regle(frais)}