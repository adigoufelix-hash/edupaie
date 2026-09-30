import sqlite3

conn = sqlite3.connect("data/edupaie.db")
with open("data/schema.sql", encoding="utf-8") as f:
    conn.executescript(f.read())
conn.close()
print("Base créée.")
