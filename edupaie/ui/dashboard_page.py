from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table

COULEURS = {"Soldé": "#2e7d32", "Partiellement payé": "#ef6c00",
            "Non payé": "#c62828"}



class Carte(QFrame):
    def __init__(self, titre):
        super().__init__()
        self.setObjectName("carte")
        libelle = QLabel(titre)
        libelle.setObjectName("titreCarte")
        self.valeur = QLabel("0")
        self.valeur.setObjectName("valeurCarte")
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(libelle)
        mise_en_page.addWidget(self.valeur)


class DashboardPage(QWidget):
    def __init__(self, paiement_service):
        super().__init__()
        self.service = paiement_service
        self.cartes = {
            "nb_eleves": Carte("Nombre d'élèves"),
            "total_encaisse": Carte("Total encaissé"),
            "total_restant": Carte("Total restant dû"),
            "nb_non_soldes": Carte("Élèves non soldés"),
        }
        haut = QHBoxLayout()
        for carte in self.cartes.values():
            haut.addWidget(carte)

        self.filtre = QComboBox()
        self.filtre.addItem("Tous les statuts", None)
        for statut in ("Non payé", "Partiellement payé", "Soldé"):
            self.filtre.addItem(statut, statut)
        self.filtre.currentIndexChanged.connect(self.recharger)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Élève", "Classe", "Total dû", "Payé", "Solde", "Statut"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)

        mise_en_page = QVBoxLayout(self)
        mise_en_page.addLayout(haut)
        mise_en_page.addWidget(QLabel("<b>Élèves par statut de paiement</b>"))
        mise_en_page.addWidget(self.filtre)
        mise_en_page.addWidget(self.table)
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()  # chiffres à jour à chaque affichage de la page

    def recharger(self):
        d = self.service.tableau_de_bord()
        self.cartes["nb_eleves"].valeur.setText(str(d["nb_eleves"]))
        self.cartes["total_encaisse"].valeur.setText(fcfa(d["total_encaisse"]))
        self.cartes["total_restant"].valeur.setText(fcfa(d["total_restant"]))
        self.cartes["nb_non_soldes"].valeur.setText(str(d["nb_non_soldes"]))

        lignes = self.service.situations(statut=self.filtre.currentData())
        lignes.sort(key=lambda ligne: ligne[1].solde, reverse=True)
        self.table.setRowCount(len(lignes))
        for i, (e, s) in enumerate(lignes):
            valeurs = [f"{e.nom} {e.prenom}", e.classe, fcfa(s.total_du),
                       fcfa(s.total_paye), fcfa(s.solde), s.statut]
            for col, texte in enumerate(valeurs):
                self.table.setItem(i, col, QTableWidgetItem(texte))
            self.table.item(i, 5).setForeground(QColor(COULEURS[s.statut]))