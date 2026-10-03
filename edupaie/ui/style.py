from PySide6.QtWidgets import QHeaderView

STYLE = """
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #1f2937; }
QMainWindow, QDialog { background: #f4f6fb; }

/* Menu latéral */
QWidget#cote { background: #1e1b4b; }
QLabel#marque { color: white; font-size: 20px; font-weight: bold; padding: 22px 16px 14px 16px; }
QListWidget#menu { background: #1e1b4b; border: none; outline: none; }
QListWidget#menu::item { color: #c7d2fe; padding: 12px 18px; margin: 2px 10px; border-radius: 8px; }
QListWidget#menu::item:hover { background: #312e81; }
QListWidget#menu::item:selected { background: #4f46e5; color: white; }

/* Boutons */
QPushButton { background: #4f46e5; color: white; border: none; border-radius: 8px;
              padding: 9px 18px; font-weight: 600; min-width: 70px; }
QPushButton:hover { background: #4338ca; }
QPushButton:pressed { background: #3730a3; }
QPushButton#danger { background: #dc2626; }
QPushButton#danger:hover { background: #b91c1c; }

/* Champs */
QLineEdit, QComboBox, QDateEdit { background: white; border: 1px solid #cbd5e1;
                                  border-radius: 8px; padding: 7px 10px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 1px solid #4f46e5; }

/* Tableaux */
QTableWidget { background: white; alternate-background-color: #f8fafc; border: 1px solid #e5e7eb;
               border-radius: 10px; selection-background-color: #e0e7ff;
               selection-color: #1e1b4b; }
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section { background: #eef2ff; color: #3730a3; font-weight: bold;
                       padding: 10px 8px; border: none; border-bottom: 2px solid #c7d2fe; }

/* Tableau de bord et fiche */
QFrame#carte { background: white; border: 1px solid #e5e7eb; border-radius: 12px; }
QLabel#titreCarte { color: #6b7280; font-size: 12px; }
QLabel#valeurCarte { color: #1e1b4b; font-size: 24px; font-weight: bold; }
QLabel#entete { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
QWidget#fondPage { background: #f4f6fb; }
QScrollArea { border: none; background: #f4f6fb; }
QFrame#panneau { background: white; border: 1px solid #e5e7eb; border-radius: 12px; }
QFrame#ligneRecente { background: #f8fafc; border: 1px solid #eef0f4; border-radius: 10px; }
QLabel#titrePage { font-size: 24px; font-weight: bold; color: #1e1b4b; }
QLabel#sousTitre { color: #6b7280; }
QLabel#titrePanneau { font-size: 14px; font-weight: bold; color: #1e1b4b; }
QLabel#sousCarte { color: #9ca3af; font-size: 11px; }
"""


def preparer_table(table):
    """Réglages communs de présentation des tableaux."""
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(36)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.horizontalHeader().setHighlightSections(False)