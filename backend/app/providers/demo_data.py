"""Static reference data for the demo provider.

Ratings are on a 0-100 scale and loosely reflect long-run team strength; they
seed the deterministic generators in ``demo.py``.
"""

LEAGUES = [
    {"id": "serie-a", "name": "Serie A", "country": "Italy"},
    {"id": "premier-league", "name": "Premier League", "country": "England"},
    {"id": "la-liga", "name": "La Liga", "country": "Spain"},
    {"id": "bundesliga", "name": "Bundesliga", "country": "Germany"},
    {"id": "ligue-1", "name": "Ligue 1", "country": "France"},
    {"id": "champions-league", "name": "UEFA Champions League", "country": "Europe"},
]

# name, short, attack, defence, elo
TEAMS = {
    "serie-a": [
        ("Inter", "INT", 88, 86, 1920),
        ("Napoli", "NAP", 84, 83, 1870),
        ("Juventus", "JUV", 80, 84, 1850),
        ("Milan", "MIL", 82, 78, 1830),
        ("Atalanta", "ATA", 83, 77, 1820),
        ("Roma", "ROM", 78, 76, 1780),
        ("Lazio", "LAZ", 76, 74, 1760),
        ("Fiorentina", "FIO", 75, 73, 1750),
        ("Bologna", "BOL", 73, 75, 1740),
        ("Torino", "TOR", 68, 74, 1700),
        ("Udinese", "UDI", 66, 68, 1660),
        ("Genoa", "GEN", 64, 67, 1640),
        ("Cagliari", "CAG", 62, 64, 1610),
        ("Verona", "VER", 61, 63, 1600),
        ("Lecce", "LEC", 60, 62, 1590),
        ("Empoli", "EMP", 58, 61, 1570),
    ],
    "premier-league": [
        ("Manchester City", "MCI", 90, 85, 1950),
        ("Arsenal", "ARS", 87, 88, 1930),
        ("Liverpool", "LIV", 89, 84, 1940),
        ("Chelsea", "CHE", 82, 78, 1840),
        ("Tottenham", "TOT", 81, 74, 1810),
        ("Manchester United", "MUN", 78, 76, 1790),
        ("Newcastle", "NEW", 80, 77, 1800),
        ("Aston Villa", "AVL", 79, 75, 1795),
        ("Brighton", "BHA", 76, 72, 1760),
        ("West Ham", "WHU", 72, 70, 1710),
        ("Crystal Palace", "CRY", 70, 73, 1700),
        ("Brentford", "BRE", 71, 69, 1690),
        ("Fulham", "FUL", 69, 68, 1680),
        ("Everton", "EVE", 64, 71, 1650),
        ("Wolves", "WOL", 66, 66, 1640),
        ("Nottingham Forest", "NFO", 68, 70, 1670),
    ],
    "la-liga": [
        ("Real Madrid", "RMA", 91, 84, 1950),
        ("Barcelona", "BAR", 89, 80, 1920),
        ("Atletico Madrid", "ATM", 82, 85, 1860),
        ("Athletic Club", "ATH", 78, 79, 1800),
        ("Real Sociedad", "RSO", 76, 77, 1780),
        ("Villarreal", "VIL", 77, 72, 1760),
        ("Real Betis", "BET", 74, 72, 1740),
        ("Sevilla", "SEV", 71, 70, 1700),
        ("Valencia", "VAL", 69, 71, 1690),
        ("Girona", "GIR", 75, 70, 1730),
        ("Osasuna", "OSA", 66, 69, 1650),
        ("Celta Vigo", "CEL", 67, 66, 1640),
        ("Mallorca", "MLL", 63, 68, 1620),
        ("Getafe", "GET", 61, 69, 1610),
        ("Alaves", "ALA", 60, 64, 1590),
        ("Espanyol", "ESP", 62, 63, 1600),
    ],
    "bundesliga": [
        ("Bayern Munich", "BAY", 91, 82, 1930),
        ("Bayer Leverkusen", "LEV", 86, 82, 1890),
        ("Borussia Dortmund", "BVB", 83, 76, 1840),
        ("RB Leipzig", "RBL", 82, 78, 1830),
        ("Stuttgart", "STU", 80, 74, 1790),
        ("Eintracht Frankfurt", "SGE", 77, 73, 1760),
        ("Freiburg", "SCF", 72, 72, 1710),
        ("Hoffenheim", "TSG", 73, 68, 1690),
        ("Wolfsburg", "WOB", 70, 70, 1680),
        ("Borussia Monchengladbach", "BMG", 71, 67, 1670),
        ("Mainz", "M05", 66, 69, 1640),
        ("Augsburg", "FCA", 65, 66, 1620),
        ("Werder Bremen", "SVW", 68, 65, 1650),
        ("Union Berlin", "FCU", 63, 70, 1630),
        ("St. Pauli", "STP", 60, 66, 1590),
        ("Heidenheim", "HDH", 59, 62, 1570),
    ],
    "ligue-1": [
        ("PSG", "PSG", 92, 83, 1940),
        ("Monaco", "ASM", 81, 74, 1810),
        ("Marseille", "OM", 79, 73, 1790),
        ("Lille", "LIL", 77, 76, 1770),
        ("Lyon", "OL", 76, 71, 1740),
        ("Nice", "NIC", 73, 75, 1730),
        ("Lens", "RCL", 72, 73, 1710),
        ("Rennes", "REN", 71, 69, 1690),
        ("Strasbourg", "RCS", 69, 67, 1660),
        ("Toulouse", "TFC", 66, 67, 1630),
        ("Nantes", "FCN", 63, 65, 1600),
        ("Reims", "SDR", 64, 66, 1610),
        ("Montpellier", "MHSC", 61, 62, 1570),
        ("Brest", "SB29", 68, 66, 1650),
        ("Auxerre", "AJA", 60, 63, 1560),
        ("Le Havre", "HAC", 58, 61, 1540),
    ],
    "champions-league": [
        ("Manchester City", "MCI", 90, 85, 1950),
        ("Real Madrid", "RMA", 91, 84, 1950),
        ("Bayern Munich", "BAY", 91, 82, 1930),
        ("Inter", "INT", 88, 86, 1920),
        ("Liverpool", "LIV", 89, 84, 1940),
        ("Barcelona", "BAR", 89, 80, 1920),
        ("Arsenal", "ARS", 87, 88, 1930),
        ("PSG", "PSG", 92, 83, 1940),
        ("Bayer Leverkusen", "LEV", 86, 82, 1890),
        ("Atletico Madrid", "ATM", 82, 85, 1860),
        ("Borussia Dortmund", "BVB", 83, 76, 1840),
        ("Juventus", "JUV", 80, 84, 1850),
    ],
}

FIRST_NAMES = [
    "Marco", "Luca", "Diego", "Pablo", "Kevin", "Thomas", "James", "Nico",
    "Rafael", "Andre", "Victor", "Bruno", "Sergio", "Karim", "Youssef",
    "Marcus", "Emil", "Jan", "Piotr", "Milan", "Dusan", "Lautaro", "Federico",
    "Alessandro", "Gabriel", "Julian", "Florian", "Jonas", "Erik", "Sandro",
]
LAST_NAMES = [
    "Rossi", "Silva", "Martinez", "Costa", "Fernandez", "Muller", "Schmidt",
    "Johnson", "Brown", "Moreau", "Dubois", "Bianchi", "Romano", "Ricci",
    "Gonzalez", "Lopez", "Santos", "Pereira", "Nowak", "Kovac", "Jansen",
    "Petit", "Laurent", "Weber", "Wagner", "Keller", "Novak", "Horvat",
]

REFEREES = [
    ("Daniele Orsato", 4.2, 0.18, 24.1, 0.31, 0.44, 0.06),
    ("Felix Zwayer", 3.8, 0.12, 22.5, 0.26, 0.47, 0.05),
    ("Anthony Taylor", 3.5, 0.10, 20.8, 0.24, 0.46, 0.04),
    ("Clement Turpin", 4.0, 0.15, 23.0, 0.28, 0.45, 0.05),
    ("Jesus Gil Manzano", 5.1, 0.22, 26.3, 0.35, 0.43, 0.07),
    ("Michael Oliver", 3.3, 0.09, 19.9, 0.27, 0.48, 0.04),
    ("Szymon Marciniak", 3.9, 0.14, 22.8, 0.29, 0.45, 0.05),
    ("Slavko Vincic", 4.1, 0.13, 23.4, 0.27, 0.46, 0.05),
]

BOOKMAKERS = ["Bet365", "Pinnacle", "William Hill", "Unibet", "Betfair", "888sport", "Snai", "Sisal"]

FORMATIONS = ["4-3-3", "4-2-3-1", "3-5-2", "4-4-2", "3-4-2-1", "4-1-4-1"]
STYLES = ["possession", "high-press", "counter", "balanced", "low-block"]

MOTIVATION_CONTEXTS = [
    ("title race", 0.9),
    ("champions league qualification", 0.8),
    ("europa league race", 0.7),
    ("relegation battle", 0.85),
    ("derby", 0.9),
    ("mid-table, little at stake", 0.35),
    ("post-cup-final league fixture", 0.5),
    ("must-win after poor run", 0.75),
]
