from .utils import slugify

# 200–250 ATK/DEF (between Common and Rare)
UNCOMMON_CARDS = [
    # One Piece (kawaii/chibi)
    {"id": slugify("Chibi Franky"), "name": "Chibi Franky", "series": "One Piece",
     "element": "Tech", "atk": 240, "def": 220},
    {"id": slugify("Chibi Brook"), "name": "Chibi Brook", "series": "One Piece",
     "element": "Spirit", "atk": 230, "def": 230},
    {"id": slugify("Chibi Vivi"), "name": "Chibi Vivi", "series": "One Piece",
     "element": "Water", "atk": 210, "def": 240},
    {"id": slugify("Chibi Jinbe"), "name": "Chibi Jinbe", "series": "One Piece",
     "element": "Water", "atk": 245, "def": 220},

    # Dragon Ball (kawaii/chibi)
    {"id": slugify("Chibi Gohan (Kid)"), "name": "Chibi Gohan (Kid)", "series": "Dragon Ball",
     "element": "Light", "atk": 235, "def": 235},
    {"id": slugify("Chibi Android 18"), "name": "Chibi Android 18", "series": "Dragon Ball",
     "element": "Tech", "atk": 250, "def": 210},
    {"id": slugify("Chibi Krillin (Training)"), "name": "Chibi Krillin (Training)", "series": "Dragon Ball",
     "element": "Spirit", "atk": 225, "def": 240},

    # Naruto (kawaii/chibi)
    {"id": slugify("Chibi Rock Lee"), "name": "Chibi Rock Lee", "series": "Naruto",
     "element": "Wind", "atk": 245, "def": 210},
    {"id": slugify("Chibi Tenten"), "name": "Chibi Tenten", "series": "Naruto",
     "element": "Tech", "atk": 220, "def": 245},
    {"id": slugify("Chibi Choji"), "name": "Chibi Choji", "series": "Naruto",
     "element": "Earth", "atk": 210, "def": 250},
]