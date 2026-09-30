import sqlite3

# (nom, prénom, classe, année scolaire, total dû)
ELEVES = [
    ("Kouassi", "Kofi", "6e A", "2026-2027", 100000),
    ("Mensah", "Ama", "6e A", "2026-2027", 100000),
    ("Diallo", "Fatou", "5e B", "2026-2027", 120000),
    ("Traoré", "Ibrahim", "5e B", "2026-2027", 120000),
    ("Ouédraogo", "Awa", "4e A", "2026-2027", 150000),
    ("Sow", "Moussa", "4e A", "2026-2027", 150000),
    ("Adjovi", "Grace", "3e A", "2026-2027", 180000),
    ("Bello", "Yacine", "3e A", "2026-2027", 180000),
    ("Koffi", "Esther", "6e B", "2026-2027", 100000),
    ("Camara", "Sékou", "5e A", "2026-2027", 120000),
    ("Nkrumah", "Kwame", "4e B", "2026-2027", 150000),
    ("Sanni", "Rachida", "3e B", "2026-2027", 180000),
    ("Gnassingbé", "Pascal", "6e A", "2026-2027", 100000),
    ("Houngbo", "Léa", "5e B", "2026-2027", 120000),
    ("Zongo", "Issouf", "4e A", "2026-2027", 150000),
    ("Dossou", "Marie", "3e A", "2026-2027", 180000),
]

# (n° élève, montant, date, mode), rangés par date
PAIEMENTS = [
    (1, 60000, "2026-09-02", "especes"),
    (3, 120000, "2026-09-02", "virement"),
    (5, 75000, "2026-09-03", "cheque"),
    (2, 50000, "2026-09-04", "mobile_money"),
    (7, 90000, "2026-09-04", "especes"),
    (9, 100000, "2026-09-07", "especes"),
    (4, 40000, "2026-09-08", "mobile_money"),
    (1, 40000, "2026-09-09", "especes"),
    (10, 120000, "2026-09-10", "cheque"),
    (6, 50000, "2026-09-11", "especes"),
    (11, 150000, "2026-09-14", "virement"),
    (2, 25000, "2026-09-15", "mobile_money"),
    (7, 45000, "2026-09-16", "especes"),
    (5, 40000, "2026-09-17", "especes"),
    (12, 60000, "2026-09-18", "cheque"),
    (4, 30000, "2026-09-21", "mobile_money"),
    (14, 120000, "2026-09-22", "especes"),
    (6, 30000, "2026-09-25", "mobile_money"),
    (12, 40000, "2026-09-28", "especes"),
]

conn = sqlite3.connect("data/edupaie.db")
conn.execute("PRAGMA foreign_keys = ON")

if conn.execute("SELECT COUNT(*) FROM eleve").fetchone()[0] > 0:
    print("La base contient déjà des données, rien à faire.")
    raise SystemExit

with conn:  # une seule transaction : tout ou rien
    conn.executemany(
        "INSERT INTO eleve (nom, prenom, classe, annee_scolaire, total_du) "
        "VALUES (?, ?, ?, ?, ?)", ELEVES)

    deja_paye = {}
    for eleve_id, montant, date, mode in PAIEMENTS:
        total_du = ELEVES[eleve_id - 1][4]
        paye = deja_paye.get(eleve_id, 0) + montant
        deja_paye[eleve_id] = paye
        cur = conn.execute(
            "INSERT INTO paiement (eleve_id, montant, date_paiement, mode, solde_apres) "
            "VALUES (?, ?, ?, ?, ?)",
            (eleve_id, montant, date, mode, total_du - paye))
        numero = f"REC-{date[:4]}-{cur.lastrowid:06d}"
        conn.execute("UPDATE paiement SET numero_recu = ? WHERE id = ?",
                     (numero, cur.lastrowid))

# Vérification : total dû, total payé et solde par élève
rows = conn.execute("""
    SELECT e.nom, e.prenom, e.total_du,
           COALESCE(SUM(p.montant), 0) AS paye,
           e.total_du - COALESCE(SUM(p.montant), 0) AS solde
    FROM eleve e LEFT JOIN paiement p ON p.eleve_id = e.id
    GROUP BY e.id ORDER BY e.id
""").fetchall()
for r in rows:
    print(r)
conn.close()