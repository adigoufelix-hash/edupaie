from dataclasses import dataclass


@dataclass
class Eleve:
    id: int | None
    nom: str
    prenom: str
    classe: str
    annee_scolaire: str
    total_du: int