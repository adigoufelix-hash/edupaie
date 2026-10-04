from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QAbstractItemView)

from edupaie.ui.paiement_dialog import MODES, fcfa
from edupaie.ui.style import preparer_table
from edupaie.ui.widgets import (AnneauProgression, CarteKpi, avatar,
                                cellule_pastille, pastille)


class DashboardPage(QWidget):
    def __init__(self, paiement_service):
        super().__init__()
        self.service = paiement_service
        self.libelles_modes = {valeur: libelle for libelle, valeur in MODES}

        titre = QLabel("Tableau de bord")
        titre.setObjectName("titrePage")
        date = QLabel(f"Situation au {QDate.currentDate().toString('dd/MM/yyyy')}")
        date.setObjectName("sousTitre")

        self.k_eleves = CarteKpi("👥", "Élèves", "#e0e7ff")
        self.k_encaisse = CarteKpi("💰", "Total encaissé", "#dcfce7")
        self.k_restant = CarteKpi("⏳", "Total restant dû", "#fef3c7")
        self.k_non_soldes = CarteKpi("⚠", "Élèves non soldés", "#fee2e2")
        cartes = QHBoxLayout()
        for carte in (self.k_eleves, self.k_encaisse, self.k_restant, self.k_non_soldes):
            cartes.addWidget(carte, 1)

        # Panneau de gauche : anneau de recouvrement
        self.anneau = AnneauProgression()
        self.p_soldes = pastille("0 soldés", "#dcfce7", "#166534")
        self.p_partiels = pastille("0 partiels", "#ffedd5", "#9a3412")
        self.p_non_payes = pastille("0 non payés", "#fee2e2", "#991b1b")
        puces = QHBoxLayout()
        for p in (self.p_soldes, self.p_partiels, self.p_non_payes):
            puces.addWidget(p)
        legende = QLabel("Encaissé / Dû")
        legende.setObjectName("sousTitre")
        gauche = QFrame()
        gauche.setObjectName("panneau")
        colonne = QVBoxLayout(gauche)
        colonne.setContentsMargins(16, 14, 16, 14)
        titre_gauche = QLabel("Recouvrement")
        titre_gauche.setObjectName("titrePanneau")
        colonne.addWidget(titre_gauche)
        colonne.addWidget(self.anneau, 1)
        colonne.addWidget(legende, alignment=Qt.AlignmentFlag.AlignHCenter)
        colonne.addLayout(puces)

        # Panneau de droite : derniers paiements
        self.liste_recents = QVBoxLayout()
        droite = QFrame()
        droite.setObjectName("panneau")
        colonne_d = QVBoxLayout(droite)
        colonne_d.setContentsMargins(16, 14, 16, 14)
        titre_droite = QLabel("Derniers paiements")
        titre_droite.setObjectName("titrePanneau")
        colonne_d.addWidget(titre_droite)
        colonne_d.addLayout(self.liste_recents)

        milieu = QHBoxLayout()
        milieu.addWidget(gauche, 2)
        milieu.addWidget(droite, 3)

        # Liste des élèves filtrable par statut
        titre_liste = QLabel("Élèves par statut de paiement")
        titre_liste.setObjectName("titrePanneau")
        self.filtre = QComboBox()
        self.filtre.addItem("Tous les statuts", None)
        for statut in ("Non payé", "Partiellement payé", "Soldé"):
            self.filtre.addItem(statut, statut)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Élève", "Classe", "Total dû", "Payé", "Solde", "Statut"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        preparer_table(self.table)
        self.table.setMinimumHeight(340)
        self.filtre.currentIndexChanged.connect(self._remplir_table)
        entete_liste = QHBoxLayout()
        entete_liste.addWidget(titre_liste, 1)
        entete_liste.addWidget(self.filtre)

        contenu = QWidget()
        contenu.setObjectName("fondPage")
        racine = QVBoxLayout(contenu)
        racine.setSpacing(14)
        racine.addWidget(titre)
        racine.addWidget(date)
        racine.addLayout(cartes)
        racine.addLayout(milieu)
        racine.addLayout(entete_liste)
        racine.addWidget(self.table)

        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        defilement.setWidget(contenu)
        externe = QVBoxLayout(self)
        externe.setContentsMargins(0, 0, 0, 0)
        externe.addWidget(defilement)
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()  # chiffres à jour à chaque affichage

    def recharger(self):
        d = self.service.tableau_de_bord()
        total_du = d["total_encaisse"] + d["total_restant"]
        taux = 100 * d["total_encaisse"] / total_du if total_du else 0
        self.k_eleves.maj(str(d["nb_eleves"]), f"{d['nb_soldes']} soldé(s)")
        self.k_encaisse.maj(fcfa(d["total_encaisse"]), f"sur {fcfa(total_du)} dus")
        self.k_restant.maj(fcfa(d["total_restant"]), "en attente de paiement")
        self.k_non_soldes.maj(str(d["nb_non_soldes"]), "à relancer")
        self.anneau.definir(taux)
        self.p_soldes.setText(f"{d['nb_soldes']} soldés")
        self.p_partiels.setText(f"{d['nb_partiels']} partiels")
        self.p_non_payes.setText(f"{d['nb_non_payes']} non payés")
        self._remplir_recents()
        self._remplir_table()

    def _remplir_recents(self):
        while self.liste_recents.count():
            element = self.liste_recents.takeAt(0)
            if element.widget():
                element.widget().deleteLater()
        for eleve, p in self.service.derniers_paiements(6):
            ligne = QFrame()
            ligne.setObjectName("ligneRecente")
            mise = QHBoxLayout(ligne)
            mise.setContentsMargins(10, 8, 10, 8)
            mise.addWidget(avatar(eleve.nom, eleve.prenom))
            mise.addWidget(QLabel(f"{eleve.nom} {eleve.prenom}"), 1)
            mise.addWidget(pastille(self.libelles_modes.get(p.mode, p.mode),
                                    "#eef2ff", "#3730a3"))
            montant = QLabel(fcfa(p.montant))
            montant.setStyleSheet("font-weight:bold;")
            mise.addWidget(montant)
            self.liste_recents.addWidget(ligne)
        self.liste_recents.addStretch()

    def _remplir_table(self):
        lignes = self.service.situations(statut=self.filtre.currentData())
        lignes.sort(key=lambda ligne: ligne[1].solde, reverse=True)
        self.table.setRowCount(len(lignes))
        for i, (e, s) in enumerate(lignes):
            valeurs = [f"{e.nom} {e.prenom}", e.classe, fcfa(s.total_du),
                       fcfa(s.total_paye), fcfa(s.solde)]
            for col, texte in enumerate(valeurs):
                self.table.setItem(i, col, QTableWidgetItem(texte))
            self.table.setCellWidget(i, 5, cellule_pastille(s.statut))