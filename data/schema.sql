PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS eleve (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT    NOT NULL,
    prenom         TEXT    NOT NULL,
    classe         TEXT    NOT NULL,
    annee_scolaire TEXT    NOT NULL,
    total_du       INTEGER NOT NULL CHECK (total_du >= 0)
);

CREATE TABLE IF NOT EXISTS paiement (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    eleve_id      INTEGER NOT NULL
                  REFERENCES eleve(id) ON DELETE RESTRICT,
    numero_recu   TEXT    UNIQUE,
    montant       INTEGER NOT NULL CHECK (montant > 0),
    date_paiement TEXT    NOT NULL,
    mode          TEXT    NOT NULL
                  CHECK (mode IN ('especes','cheque','virement','mobile_money')),
    solde_apres   INTEGER NOT NULL CHECK (solde_apres >= 0)
);

CREATE INDEX IF NOT EXISTS idx_paiement_eleve ON paiement(eleve_id);

CREATE TABLE annee_scolaire (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle TEXT NOT NULL UNIQUE,      -- ex: "2026-2027"
    date_debut TEXT NOT NULL,
    date_fin TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0  -- une seule active à la fois
);

CREATE TABLE classe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,                 -- ex: "6ème A"
    niveau TEXT NOT NULL,              -- ex: "6ème"
    annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
    UNIQUE (nom, annee_id)
);

CREATE TABLE frais_classe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classe_id INTEGER NOT NULL REFERENCES classe(id),
    libelle TEXT NOT NULL,             -- ex: "Scolarité T1"
    montant INTEGER NOT NULL,          -- en FCFA, sans décimales
    date_echeance TEXT
);

-- Lier chaque élève à une classe
ALTER TABLE eleve ADD COLUMN classe_id INTEGER REFERENCES classe(id);