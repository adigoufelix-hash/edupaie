# edupaie
Application Desktop de gestion des payements des écoles

# EduPaie - Gestion des paiements scolaires

Application de bureau (Python, PySide6, SQLite) pour enregistrer les élèves
et leurs paiements, calculer le solde restant dû et éditer des reçus PDF numérotés.

## Fonctionnalités
- Gestion des élèves (ajout, modification, suppression, recherche, filtre par classe)
- Enregistrement des paiements (espèces, chèque, virement, mobile money)
- Solde et statut automatiques (Soldé / Partiellement payé / Non payé)
- Historique des paiements par élève
- Reçu PDF numéroté, réimprimable à l'identique
- Tableau de bord (élèves, total encaissé, restant dû, non soldés)

## Installation (développement)
Prérequis : Python 3.10 ou supérieur.

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python main.py

## Tests
    python -m unittest discover -v

## Architecture
- `edupaie/repositories` : accès aux données (tout le SQL)
- `edupaie/services` : logique métier (soldes, validations, numéro de reçu, PDF)
- `edupaie/ui` : interface PySide6 (aucune requête SQL)
- `data/schema.sql` : création des tables ; `data/edupaie.db` : base de test
  (16 élèves, 19 paiements)

## Exécutable Windows
Construit avec PyInstaller :

    pyinstaller --onefile --windowed --name EduPaie --add-data "data/edupaie.db;data" main.py

Copier `EduPaie.exe` dans un dossier et le lancer : le dossier `data` avec la base
est créé à côté de l'exécutable. Les reçus sont enregistrés dans
`Documents` > `EduPaie\recus` (dossier utilisateur).

## Gestion de version
Une branche par fonctionnalité (`feature/gestion-eleves`, `feature/paiement`,
`feature/solde`, `feature/historique`, `feature/recu`, `feature/dashboard`),
fusionnées dans `main`.
