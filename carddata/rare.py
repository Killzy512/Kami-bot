from .utils import slugify

# 260–380 ATK/DEF
RARE_CARDS = [
    {"id": slugify("Chibi Zoro"), "name": "Chibi Zoro", "series": "One Piece",
     "element": "Wind", "atk": 340, "def": 300},
    {"id": slugify("Chibi Sanji"), "name": "Chibi Sanji", "series": "One Piece",
     "element": "Fire", "atk": 320, "def": 300},
    {"id": slugify("Chibi Nico Robin"), "name": "Chibi Nico Robin", "series": "One Piece",
     "element": "Dark", "atk": 280, "def": 360},
    {"id": slugify("Chibi Trunks"), "name": "Chibi Trunks", "series": "Dragon Ball",
     "element": "Tech", "atk": 350, "def": 290},
    {"id": slugify("Chibi Piccolo"), "name": "Chibi Piccolo", "series": "Dragon Ball",
     "element": "Spirit", "atk": 360, "def": 300},
    {"id": slugify("Chibi Sakura"), "name": "Chibi Sakura", "series": "Naruto",
     "element": "Spirit", "atk": 300, "def": 340},
    {"id": slugify("Chibi Gaara"), "name": "Chibi Gaara", "series": "Naruto",
     "element": "Earth", "atk": 360, "def": 280},
    {"id": slugify("Chibi Kakashi"), "name": "Chibi Kakashi", "series": "Naruto",
     "element": "Wind", "atk": 330, "def": 310},
]