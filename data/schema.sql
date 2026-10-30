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
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    login            TEXT NOT NULL UNIQUE,
    nom_complet      TEXT NOT NULL,
    mot_de_passe     TEXT NOT NULL,   -- format : iterations$sel$hash (hex)
    role             TEXT NOT NULL CHECK (role IN ('admin', 'comptable', 'lecture')),
    actif            INTEGER NOT NULL DEFAULT 1,
    doit_changer_mdp INTEGER NOT NULL DEFAULT 0,
    cree_le          TEXT NOT NULL DEFAULT (datetime('now'))
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
    encaisse_par   TEXT,   -- nom du caissier au moment du paiement
    annule           INTEGER NOT NULL DEFAULT 0,
    motif_annulation TEXT,
    annule_par       TEXT,
    annule_le        TEXT
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
CREATE TABLE IF NOT EXISTS remise (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    eleve_id         INTEGER NOT NULL REFERENCES eleve(id) ON DELETE CASCADE,
    type             TEXT    NOT NULL CHECK (type IN ('montant', 'pourcentage')),
    valeur           INTEGER NOT NULL CHECK (valeur > 0),
    montant          INTEGER NOT NULL CHECK (montant > 0),  -- montant effectif, figé
    motif            TEXT    NOT NULL,
    accorde_par      TEXT,
    accorde_le       TEXT    NOT NULL,
    annule           INTEGER NOT NULL DEFAULT 0,
    motif_annulation TEXT,
    annule_par       TEXT,
    annule_le        TEXT
);

CREATE INDEX IF NOT EXISTS idx_remise_eleve ON remise(eleve_id);

CREATE TABLE IF NOT EXISTS echeance (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    classe         TEXT    NOT NULL,
    annee_scolaire TEXT    NOT NULL,
    libelle        TEXT    NOT NULL COLLATE NOCASE,
    date_limite    TEXT    NOT NULL,
    pourcentage    INTEGER NOT NULL CHECK (pourcentage BETWEEN 1 AND 100),
    UNIQUE (classe, annee_scolaire, libelle)
);

CREATE TABLE IF NOT EXISTS contact_eleve (
    eleve_id  INTEGER PRIMARY KEY REFERENCES eleve(id) ON DELETE CASCADE,
    tuteur    TEXT,
    telephone TEXT
);

CREATE TABLE IF NOT EXISTS ecole (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    nom       TEXT NOT NULL,
    adresse   TEXT,
    telephone TEXT,
    email     TEXT,
    logo      BLOB,
    couleur   TEXT
);
CREATE TABLE IF NOT EXISTS classe (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nom   TEXT NOT NULL COLLATE NOCASE UNIQUE,
    ordre INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS parametre (
    cle    TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date_heure     TEXT    NOT NULL,
    utilisateur_id INTEGER,
    utilisateur    TEXT,
    action         TEXT    NOT NULL,
    objet          TEXT,
    objet_id       INTEGER,
    detail         TEXT    NOT NULL DEFAULT '',
    hash           TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_date ON audit(date_heure);

CREATE TRIGGER IF NOT EXISTS audit_pas_de_modification
BEFORE UPDATE ON audit
BEGIN
    SELECT RAISE(ABORT, 'Le journal d''audit ne peut pas être modifié.');
END;

CREATE TRIGGER IF NOT EXISTS audit_pas_de_suppression
BEFORE DELETE ON audit
BEGIN
    SELECT RAISE(ABORT, 'Le journal d''audit ne peut pas être supprimé.');
END;

CREATE TABLE IF NOT EXISTS code_secours (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateur(id) ON DELETE CASCADE,
    empreinte      TEXT NOT NULL,
    utilise_le     TEXT
);

CREATE INDEX IF NOT EXISTS idx_code_secours_utilisateur ON code_secours(utilisateur_id);

CREATE TABLE IF NOT EXISTS passage (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    eleve_ancien_id  INTEGER NOT NULL REFERENCES eleve(id) ON DELETE CASCADE,
    eleve_nouveau_id INTEGER NOT NULL REFERENCES eleve(id) ON DELETE CASCADE,
    annee_source     TEXT NOT NULL,
    annee_cible      TEXT NOT NULL,
    classe_source    TEXT NOT NULL,
    classe_cible     TEXT NOT NULL,
    arrieres         INTEGER NOT NULL DEFAULT 0,
    fait_le          TEXT NOT NULL,
    fait_par         TEXT,
    UNIQUE (eleve_ancien_id, annee_cible)
);