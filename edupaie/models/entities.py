from dataclasses import dataclass


@dataclass
class Eleve:
    id: int | None
    nom: str
    prenom: str
    classe: str
    annee_scolaire: str
    total_du: int
 
@dataclass
class Paiement:
        id: int | None
        eleve_id: int
        numero_recu: str | None
        montant: int
        date_paiement: str
        mode: str
        solde_apres: int