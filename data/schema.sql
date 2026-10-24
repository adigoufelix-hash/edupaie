PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS eleve (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT    NOT NULL,
    prenom         TEXT    NOT NULL,
    classe         TEXT    NOT NULL,
    annee_scolaire TEXT    NOT NULL,
    total_du       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS utilisateur (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT NOT NULL UNIQUE,
    nom_complet   TEXT NOT NULL,
    mot_de_passe  TEXT NOT NULL,   -- format : iterations$sel$hash (hex)
    role          TEXT NOT NULL CHECK (role IN ('admin', 'comptable', 'lecture')),
    actif         INTEGER NOT NULL DEFAULT 1,
    cree_le       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS paiement (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    eleve_id       INTEGER NOT NULL
                   REFERENCES eleve(id) ON DELETE RESTRICT,
    numero_recu    TEXT    UNIQUE,
    montant        INTEGER NOT NULL CHECK (montant > 0),
    date_paiement  TEXT    NOT NULL,
    mode           TEXT    NOT NULL
                   CHECK (mode IN ('especes','cheque','virement','mobile_money')),
    solde_apres    INTEGER NOT NULL CHECK (solde_apres >= 0),
    utilisateur_id INTEGER REFERENCES utilisateur(id) ON DELETE SET NULL,
    encaisse_par   TEXT    -- nom du caissier au moment du paiement
);

CREATE INDEX IF NOT EXISTS idx_paiement_eleve ON paiement(eleve_id);

CREATE TABLE IF NOT EXISTS frais_classe (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    classe         TEXT    NOT NULL,
    annee_scolaire TEXT    NOT NULL,
    libelle        TEXT    NOT NULL COLLATE NOCASE,
    montant        INTEGER NOT NULL CHECK (montant > 0),
    UNIQUE (classe, annee_scolaire, libelle)
);