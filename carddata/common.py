from .utils import slugify

# 100–200 ATK/DEF
COMMON_CARDS = [
    {"id": slugify("Chibi Luffy"), "name": "Chibi Luffy", "series": "One Piece",
     "element": "Spirit", "atk": 170, "def": 160},
    {"id": slugify("Chibi Nami"), "name": "Chibi Nami", "series": "One Piece",
     "element": "Water", "atk": 150, "def": 180},
    {"id": slugify("Chibi Usopp"), "name": "Chibi Usopp", "series": "One Piece",
     "element": "Tech", "atk": 160, "def": 140},
    {"id": slugify("Chibi Chopper"), "name": "Chibi Chopper", "series": "One Piece",
     "element": "Earth", "atk": 140, "def": 190},
    {"id": slugify("Chibi Krillin"), "name": "Chibi Krillin", "series": "Dragon Ball",
     "element": "Light", "atk": 180, "def": 160},
    {"id": slugify("Chibi Bulma"), "name": "Chibi Bulma", "series": "Dragon Ball",
     "element": "Tech", "atk": 190, "def": 150},
    {"id": slugify("Chibi Hinata"), "name": "Chibi Hinata", "series": "Naruto",
     "element": "Spirit", "atk": 170, "def": 170},
    {"id": slugify("Chibi Konohamaru"), "name": "Chibi Konohamaru", "series": "Naruto",
     "element": "Fire", "atk": 160, "def": 160},
]