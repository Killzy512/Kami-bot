from .utils import slugify

# 360–520 ATK/DEF
EPIC_CARDS = [
    {"id": slugify("Chibi Luffy (Gear 2)"), "name": "Chibi Luffy (Gear 2)", "series": "One Piece",
     "element": "Spirit", "atk": 480, "def": 440},
    {"id": slugify("Chibi Zoro (Asura)"), "name": "Chibi Zoro (Asura)", "series": "One Piece",
     "element": "Wind", "atk": 510, "def": 410},
    {"id": slugify("Chibi Sanji (Diable)"), "name": "Chibi Sanji (Diable Jambe)", "series": "One Piece",
     "element": "Fire", "atk": 470, "def": 430},
    {"id": slugify("Chibi Bulma (Battle Suit)"), "name": "Chibi Bulma (Battle Suit)", "series": "Dragon Ball",
     "element": "Tech", "atk": 420, "def": 500},
    {"id": slugify("Chibi Vegeta (SSJ)"), "name": "Chibi Vegeta (SSJ)", "series": "Dragon Ball",
     "element": "Light", "atk": 500, "def": 420},
    {"id": slugify("Chibi Naruto (Sage)"), "name": "Chibi Naruto (Sage)", "series": "Naruto",
     "element": "Spirit", "atk": 500, "def": 420},
    {"id": slugify("Chibi Itachi"), "name": "Chibi Itachi", "series": "Naruto",
     "element": "Dark", "atk": 500, "def": 400},
    {"id": slugify("Chibi Tsunade"), "name": "Chibi Tsunade", "series": "Naruto",
     "element": "Earth", "atk": 440, "def": 500},
]