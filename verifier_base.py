import sqlite3
import sys

CHEMIN = sys.argv[1] if len(sys.argv) > 1 else "data/edupaie.db"
conn = sqlite3.connect(CHEMIN)

nb_eleves = conn.execute("SELECT COUNT(*) FROM eleve").fetchone()[0]
nb_paiements = conn.execute("SELECT COUNT(*) FROM paiement").fetchone()[0]
classes = conn.execute("SELECT COUNT(DISTINCT classe) FROM eleve").fetchone()[0]

statuts = dict(conn.execute("""
    SELECT statut, COUNT(*) FROM (
        SELECT CASE
                 WHEN COALESCE(SUM(p.montant), 0) >= e.total_du THEN 'Soldé'
                 WHEN COALESCE(SUM(p.montant), 0) = 0 THEN 'Non payé'
                 ELSE 'Partiellement payé'
               END AS statut
        FROM eleve e LEFT JOIN paiement p ON p.eleve_id = e.id
        GROUP BY e.id)
    GROUP BY statut""").fetchall())

modes = [r[0] for r in conn.execute(
    "SELECT DISTINCT mode FROM paiement ORDER BY mode")]
sans_numero = conn.execute(
    "SELECT COUNT(*) FROM paiement WHERE numero_recu IS NULL").fetchone()[0]
incoherents = conn.execute("""
    SELECT COUNT(*) FROM paiement p JOIN eleve e ON e.id = p.eleve_id
    WHERE p.solde_apres <> e.total_du - (
        SELECT SUM(q.montant) FROM paiement q
        WHERE q.eleve_id = p.eleve_id AND q.id <= p.id)""").fetchone()[0]

print(f"Base : {CHEMIN}")
print(f"Eleves : {nb_eleves} | Paiements : {nb_paiements} | Classes : {classes}")
for nom in ("Soldé", "Partiellement payé", "Non payé"):
    print(f"  {nom} : {statuts.get(nom, 0)}")
print("Modes utilisés :", ", ".join(modes))
print("Reçus sans numéro :", sans_numero)
print("Soldes incohérents :", incoherents)

conforme = (nb_eleves >= 15 and sans_numero == 0 and incoherents == 0
            and all(statuts.get(n, 0) > 0
                    for n in ("Soldé", "Partiellement payé", "Non payé")))
print("RESULTAT :", "CONFORME au livrable 3" if conforme else "NON CONFORME")