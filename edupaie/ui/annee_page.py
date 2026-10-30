from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from edupaie.services.annee_service import annee_suivante
from edupaie.services.export_passage import exporter_passage
from edupaie.services.paiement_service import ErreurMetier
from edupaie.ui.fichiers import apres_export
from edupaie.ui.paiement_dialog import fcfa
from edupaie.ui.style import preparer_table

SORTIE = "— Sortie (non réinscrit) —"
LIBELLES_STATUT = {"a_faire": "", "fait": "Déjà réinscrit", "inscrit": "Déjà inscrit"}


class PassageDialog(QDialog):
    def __init__(self, service, source, parent=None):
        super().__init__(parent)
        self.service = service
        self.proposition = service.proposer(source)  # ErreurMetier gérée par l'appelant
        self.source = self.proposition["source"]
        self.cible = self.proposition["cible"]
        self.lignes = self.proposition["lignes"]
        self.classes = service.classes()
        self._frais = {}
        self.setWindowTitle(f"Passage de {self.source} à {self.cible}")
        self.resize(1080, 700)

        aide = QLabel(
            f"Vérifie la nouvelle classe de chaque élève (proposée d'après l'ordre de tes "
            f"classes), décoche ceux qui ne reviennent pas, puis lance le passage. Une "
            f"nouvelle fiche est créée pour {self.cible} ; les fiches {self.source} et leurs "
            "paiements sont conservés.")
        aide.setWordWrap(True)

        # Changement en bloc : toute une classe vers une destination
        self.bloc_source = QComboBox()
        for c in self.classes:
            if any(l["classe"].casefold() == c.casefold() for l in self.lignes):
                self.bloc_source.addItem(c, c)
        self.bloc_destination = QComboBox()
        self._remplir_destinations(self.bloc_destination)
        appliquer = QPushButton("Appliquer à toute la classe")
        appliquer.clicked.connect(self._appliquer_en_bloc)
        bloc = QHBoxLayout()
        bloc.addWidget(QLabel("Toute la classe"))
        bloc.addWidget(self.bloc_source, 1)
        bloc.addWidget(QLabel("va en"))
        bloc.addWidget(self.bloc_destination, 1)
        bloc.addWidget(appliquer)

        self.table = QTableWidget(len(self.lignes), 6)
        self.table.setHorizontalHeaderLabels(
            ["Réinscrire", "Élève", "Classe actuelle", "Nouvelle classe", "Arriéré", "État"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        preparer_table(self.table)
        self.combos = []
        for i, l in enumerate(self.lignes):
            a_faire = l["statut"] == "a_faire"
            case = QTableWidgetItem()
            case.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                          if a_faire else Qt.ItemFlag.ItemIsEnabled)
            case.setCheckState(Qt.CheckState.Checked if a_faire and l["destination"]
                               else Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, case)
            self.table.setItem(i, 1, QTableWidgetItem(f"{l['nom']} {l['prenom']}"))
            self.table.setItem(i, 2, QTableWidgetItem(l["classe"]))
            combo = QComboBox()
            self._remplir_destinations(combo)
            if l["destination"]:
                combo.setCurrentIndex(max(combo.findData(l["destination"]), 0))
            combo.setEnabled(a_faire)
            combo.currentIndexChanged.connect(lambda _=0, r=i: self._destination_changee(r))
            self.table.setCellWidget(i, 3, combo)
            self.combos.append(combo)
            self.table.setItem(i, 4, QTableWidgetItem(fcfa(l["arrieres"])))
            self.table.setItem(i, 5, QTableWidgetItem(LIBELLES_STATUT[l["statut"]]))

        self.reporter = QCheckBox(
            "Reporter les arriérés sur la nouvelle année (l'ancienne fiche est soldée par "
            "une remise « Arriéré reporté »)")
        self.reporter.setChecked(True)
        self.resume = QLabel()
        self.resume.setTextFormat(Qt.TextFormat.RichText)
        self.resume.setWordWrap(True)
        self.lancer = QPushButton("Lancer le passage")
        annuler = QPushButton("Annuler")
        self.lancer.clicked.connect(self._lancer)
        annuler.clicked.connect(self.reject)

        bas = QHBoxLayout()
        bas.addStretch()
        bas.addWidget(self.lancer)
        bas.addWidget(annuler)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(bloc)
        mise_en_page.addWidget(self.table, 1)
        mise_en_page.addWidget(self.reporter)
        mise_en_page.addWidget(self.resume)
        mise_en_page.addLayout(bas)

        self.table.itemChanged.connect(lambda *_: self._maj_resume())
        self.reporter.toggled.connect(lambda *_: self._maj_resume())
        self._maj_resume()

    def _remplir_destinations(self, combo):
        combo.addItem(SORTIE, None)
        for c in self.classes:
            combo.addItem(c, c)

    def _destination_changee(self, ligne):
        case = self.table.item(ligne, 0)
        if self.lignes[ligne]["statut"] == "a_faire":
            case.setCheckState(Qt.CheckState.Checked
                               if self.combos[ligne].currentData() else Qt.CheckState.Unchecked)
        self._maj_resume()

    def _appliquer_en_bloc(self):
        classe = self.bloc_source.currentData()
        destination = self.bloc_destination.currentData()
        for i, l in enumerate(self.lignes):
            if l["statut"] == "a_faire" and l["classe"].casefold() == (classe or "").casefold():
                self.combos[i].setCurrentIndex(max(self.combos[i].findData(destination), 0))

    def _frais_definis(self, classe):
        if classe not in self._frais:
            self._frais[classe] = self.service.frais_definis(classe, self.cible)
        return self._frais[classe]

    def _selection(self):
        """Lignes à réinscrire : [(ligne, classe de destination)]."""
        selection = []
        for i, l in enumerate(self.lignes):
            destination = self.combos[i].currentData()
            if (l["statut"] == "a_faire" and destination
                    and self.table.item(i, 0).checkState() == Qt.CheckState.Checked):
                selection.append((l, destination))
        return selection

    def _maj_resume(self):
        selection = self._selection()
        a_faire = sum(1 for l in self.lignes if l["statut"] == "a_faire")
        arrieres = sum(l["arrieres"] for l, _ in selection) if self.reporter.isChecked() else 0
        texte = (f"<b>{len(selection)}</b> élève(s) à réinscrire en {self.cible} - "
                 f"{a_faire - len(selection)} sortant(s) - arriérés reportés : "
                 f"<b>{fcfa(arrieres)}</b>")
        sans_frais = sorted({d for _, d in selection if not self._frais_definis(d)},
                            key=str.casefold)
        if sans_frais:
            texte += ("<br><span style='color:#9a3412'>Frais non définis pour "
                      f"{self.cible} dans : {', '.join(sans_frais)}. L'ancien total sera "
                      "repris pour ces élèves : utilise d'abord « Reprendre les frais » "
                      "dans l'écran Années scolaires pour l'éviter.</span>")
        self.resume.setText(texte)
        self.lancer.setEnabled(bool(selection))

    def _lancer(self):
        selection = self._selection()
        if QMessageBox.question(
                self, "Passage à l'année suivante",
                f"Réinscrire {len(selection)} élève(s) en {self.cible} ?\n\n"
                "Une sauvegarde de la base est faite juste avant. L'année active deviendra "
                f"{self.cible}.") != QMessageBox.Yes:
            return
        plan = []
        for i, l in enumerate(self.lignes):
            if l["statut"] != "a_faire":
                continue
            destination = self.combos[i].currentData()
            plan.append({"eleve_id": l["eleve_id"], "destination": destination,
                         "reinscrire": any(l is s for s, _ in selection)})
        try:
            resultat = self.service.executer(self.source, plan, self.reporter.isChecked())
        except ErreurMetier as e:
            QMessageBox.warning(self, "Passage impossible", str(e))
            return
        message = (f"{resultat['reinscrits']} élève(s) réinscrit(s) en {resultat['cible']}, "
                   f"{resultat['sortants']} sortant(s), arriérés reportés : "
                   f"{fcfa(resultat['arrieres'])}.")
        if resultat["sans_frais"]:
            message += (f"\n{resultat['sans_frais']} élève(s) n'avaient pas de frais définis : "
                        "leur ancien total a été repris, à vérifier.")
        QMessageBox.information(self, "Passage terminé", message)
        if QMessageBox.question(
                self, "Rapport", "Enregistrer le rapport du passage au format Excel ?"
        ) == QMessageBox.Yes:
            try:
                apres_export(self, exporter_passage(resultat, "exports"))
            except OSError as e:
                QMessageBox.warning(self, "Export impossible", str(e))
        self.accept()


class AnneePage(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        titre = QLabel("<h3 style='margin:0'>Années scolaires</h3>")
        self.etat = QLabel()
        self.etat.setTextFormat(Qt.TextFormat.RichText)
        self.etat.setWordWrap(True)
        aide = QLabel(
            "L'année active est celle qu'affichent par défaut les écrans Élèves et Tableau "
            "de bord. Le passage à l'année suivante crée une nouvelle fiche pour chaque élève "
            "réinscrit ; les anciennes fiches, leurs paiements et leurs reçus sont conservés "
            "et restent consultables avec le filtre d'année de l'écran Élèves.")
        aide.setWordWrap(True)

        self.choix = QComboBox()
        definir = QPushButton("Définir comme année active")
        reprendre = QPushButton("Reprendre les frais et échéanciers de l'année précédente")
        passage = QPushButton("Préparer le passage à l'année suivante...")
        definir.clicked.connect(self._definir)
        reprendre.clicked.connect(self._reprendre)
        passage.clicked.connect(self._passage)

        ligne = QHBoxLayout()
        ligne.addWidget(QLabel("Année active"))
        ligne.addWidget(self.choix, 1)
        ligne.addWidget(definir)
        mise_en_page = QVBoxLayout(self)
        mise_en_page.addWidget(titre)
        mise_en_page.addWidget(self.etat)
        mise_en_page.addWidget(aide)
        mise_en_page.addLayout(ligne)
        mise_en_page.addSpacing(12)
        mise_en_page.addWidget(QLabel("<b>À la fin de l'année scolaire</b>"))
        mise_en_page.addWidget(reprendre)
        mise_en_page.addWidget(passage)
        mise_en_page.addStretch()
        self.recharger()

    def showEvent(self, event):
        super().showEvent(event)
        self.recharger()

    def recharger(self):
        active = self.service.active()
        annees = self.service.annees()
        self.choix.clear()
        proposees = list(annees)
        if proposees:
            suivante = annee_suivante(proposees[-1])
            if suivante not in proposees:
                proposees.append(suivante)
        for a in proposees:
            self.choix.addItem(a, a)
        if active:
            self.choix.setCurrentIndex(max(self.choix.findData(active), 0))
            self.etat.setText(f"Année active : <b>{active}</b>")
        else:
            self.etat.setText("Aucune année active : toutes les années sont affichées.")

    def _redemarrer_session(self):
        QMessageBox.information(
            self, "Année scolaire",
            "L'application va se rouvrir pour afficher la nouvelle année : reconnecte-toi.")
        self.window().deconnecter()

    def _definir(self):
        annee = self.choix.currentData()
        if not annee:
            QMessageBox.information(self, "Année active", "Aucune année à choisir.")
            return
        try:
            self.service.definir_active(annee)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Année active", str(e))
            return
        self._redemarrer_session()

    def _source(self):
        source = self.service.source_proposee()
        if source is None:
            QMessageBox.information(self, "Années scolaires",
                                    "Aucun élève n'est enregistré : rien à faire passer.")
        return source

    def _reprendre(self):
        source = self._source()
        if source is None:
            return
        cible = annee_suivante(source)
        if QMessageBox.question(
                self, "Reprendre les frais",
                f"Copier les frais et les échéanciers de {source} vers {cible} ?\n"
                "Les classes qui ont déjà des frais ou des tranches pour "
                f"{cible} ne sont pas touchées. Les dates avancent d'un an."
        ) != QMessageBox.Yes:
            return
        try:
            r = self.service.reprendre_frais(source)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Reprise impossible", str(e))
            return
        QMessageBox.information(
            self, "Reprise terminée",
            f"{r['frais_lignes']} ligne(s) de frais ({r['frais_classes']} classe(s)) et "
            f"{r['echeance_lignes']} tranche(s) d'échéancier ({r['echeance_classes']} "
            f"classe(s)) copiées vers {r['cible']}.\nTu peux les ajuster dans « Classes "
            "et frais ».")

    def _passage(self):
        source = self._source()
        if source is None:
            return
        try:
            dialogue = PassageDialog(self.service, source, self)
        except ErreurMetier as e:
            QMessageBox.warning(self, "Passage impossible", str(e))
            return
        if dialogue.exec() == QDialog.Accepted:
            self._redemarrer_session()