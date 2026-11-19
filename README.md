# EduPaie

**Gestion des paiements scolaires** : une application de bureau pour Windows qui permet à une école d'enregistrer ses élèves et leurs paiements, de calculer les soldes, d'imprimer des reçus vérifiables et de suivre le recouvrement des frais. Elle fonctionne **sans internet**, avec une base de données locale.

Projet réalisé à l'Académie Digitale Numérique (ADN Golfe 1), Lomé, à partir d'un brief de six fonctionnalités (gestion des élèves, paiement, solde, historique, reçu, tableau de bord), puis développé en produit destiné aux écoles.

## Fonctionnalités

**Encaissement et suivi**
- Élèves : ajout, modification, recherche, filtres par année, classe et statut, import depuis Excel, export Excel.
- Paiements en espèces, chèque, virement ou mobile money, avec le **n° de transaction** (unique par paiement).
- Reçus PDF numérotés, avec QR code et code de contrôle ; écran de **vérification** d'un reçu.
- Annulation d'un paiement avec motif (le paiement reste visible, barré) ; remises et bourses.
- Clôture de caisse par caissier et par mode de paiement (PDF et Excel).

**Pilotage**
- Frais par classe, échéancier en tranches, écran **Impayés**.
- **Recouvrement** : taux d'encaissement par classe et par mois (direction).
- **Relances WhatsApp** groupées : un message par parent, historique des relances.
- **Résumé de caisse** envoyé à la direction par WhatsApp.
- **Rapprochement mobile money** : import d'un relevé (Excel ou CSV) comparé aux paiements enregistrés.

**Organisation de l'école**
- Paramètres de l'école (nom, adresse, boîte postale, logo, couleur de l'application) appliqués aux documents.
- Gestion des classes, passage à l'année scolaire suivante (réinscriptions, report des arriérés).
- Trois rôles : administrateur, comptable, lecture.

**Sécurité et exploitation**
- Connexion, verrouillage après 5 minutes d'inactivité, mots de passe temporaires, codes de secours pour les administrateurs.
- **Journal d'audit** chaîné par empreintes, protégé par des déclencheurs SQL (aucune modification ni suppression).
- Sauvegardes automatiques et manuelles, restauration.
- **Guide d'utilisation** intégré (touche F1), avec recherche et liste « Pour bien démarrer ».
- Licence avec période d'essai de 30 jours (voir plus bas).

## Architecture

Une application en couches : chaque couche ne dialogue qu'avec celle du dessous.

```
Interface (PySide6)  ->  Services (règles métier)  ->  Repositories (SQL)  ->  SQLite
```

```
main.py                    point d'entrée : câblage des services, connexion, fenêtre principale
edupaie/
  db/connection.py         connexion SQLite, schéma appliqué à chaque lancement, migrations
  models/entities.py       entités (Eleve, Paiement...)
  repositories/            accès aux données, le seul endroit où l'on écrit du SQL
  services/                règles métier, validations, droits, PDF, exports Excel
  ui/                      écrans et fenêtres PySide6
  permissions.py           rôles et permissions
  references.py            règles des numéros de transaction
  version.py               numéro de version
data/schema.sql            schéma de la base de données
tests/                     tests unitaires (unittest, base SQLite en mémoire)
outils/                    outils du fournisseur : licences, construction (non livrés aux écoles)
assets/                    icône
EduPaie.spec               configuration PyInstaller
installateur.iss           script Inno Setup
```

Principes : l'interface n'écrit jamais de SQL ; les montants sont des entiers (FCFA) ; toute opération sensible passe par un service qui vérifie les droits ; le journal d'audit est alimenté automatiquement autour des services.

## Installation pour le développement

Prérequis : Python 3.10 ou plus (développé avec 3.14) et Git.

```bash
git clone https://github.com/adigoufelix-hash/edupaie.git
cd edupaie
python -m venv .venv
source .venv/Scripts/activate        # Git Bash sous Windows
pip install -r requirements.txt
python main.py
```

Au premier lancement, l'application demande de créer le compte administrateur. En développement, la base est `data/edupaie.db` (ignorée par Git).

## Tests et qualité

```bash
python -m pyflakes main.py edupaie outils
python -W ignore::ResourceWarning -m unittest
```

Les tests utilisent une base SQLite en mémoire construite depuis `data/schema.sql`.

## Où sont les données ?

| Mode | Emplacement |
|---|---|
| Développement | `data/edupaie.db`, `sauvegardes/`, `exports/`, `recus/`... à la racine du projet |
| Version installée | `%LOCALAPPDATA%\EduPaie` (base, sauvegardes, exports, reçus, `erreurs.log`) |

Ces dossiers ne doivent **jamais** être ajoutés à Git (voir `.gitignore`).

## Construire l'installateur

Prérequis : `pip install -r requirements-dev.txt` et **Inno Setup 6**.

```bash
python -m outils.construire             # version de livraison (sans console)
python -m outils.construire --console   # version d'essai (erreurs visibles)
```

Le résultat est `installateur/EduPaie_Setup_<version>.exe`. La version se règle dans `edupaie/version.py`. Les données de l'école ne sont jamais supprimées par l'installation, la mise à jour ni la désinstallation.

## Licence logicielle

EduPaie s'utilise 30 jours à l'essai, puis avec une clé de licence signée (Ed25519) et liée à l'ordinateur ; sans licence, l'application reste consultable (exports, sauvegardes) mais la saisie est bloquée.

- La **clé publique** de vérification est dans `edupaie/services/licence.py`.
- La **clé privée** ne doit jamais être dans le dépôt ni dans un installateur : elle reste chez le fournisseur (`outils/cle_privee.pem`, ignorée par Git, à sauvegarder hors de l'ordinateur).
- Émettre une licence : `python -m outils.emettre_licence`.

## Documentation

- **Guide d'utilisation** : intégré à l'application (touche F1), adapté au rôle de l'utilisateur.
- **Manuel d'installation et de prise en main** : à remettre à l'école avec l'installateur.

## Feuille de route

- Version réseau (plusieurs postes de saisie), avec un serveur de base de données.
- Rapprochement mobile money affiné avec de vrais relevés Flooz et T-Money.
- Signature de code de l'installateur.

## Auteur

ADIGOU Adélodjou Félix, étudiant en développement web à ADN Golfe 1 (Lomé). Logiciel propriétaire : tous droits réservés.
