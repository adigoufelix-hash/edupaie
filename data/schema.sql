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
