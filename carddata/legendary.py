from .utils import slugify

# 520–700 ATK/DEF
LEGENDARY_CARDS = [
    {"id": slugify("Chibi Luffy (Gear 5)"), "name": "Chibi Luffy (Gear 5)", "series": "One Piece",
        "element": "Spirit", "atk": 680, "def": 640},
    {"id": slugify("Chibi Zoro (King of Hell)"), "name": "Chibi Zoro (King of Hell)", "series": "One Piece",
        "element": "Dark", "atk": 660, "def": 640},
    {"id": slugify("Chibi Sanji (Ifrit)"), "name": "Chibi Sanji (Ifrit Jambe)", "series": "One Piece",
        "element": "Fire", "atk": 640, "def": 620},
    {"id": slugify("Chibi Shenron"), "name": "Chibi Shenron", "series": "Dragon Ball",
        "element": "Dragon", "atk": 690, "def": 650},
    {"id": slugify("Chibi Goku (UI)"), "name": "Chibi Goku (Ultra Instinct)", "series": "Dragon Ball",
        "element": "Light", "atk": 700, "def": 660},
    {"id": slugify("Chibi Vegeta (UE)"), "name": "Chibi Vegeta (Ultra Ego)", "series": "Dragon Ball",
        "element": "Dark", "atk": 680, "def": 620},
    {"id": slugify("Chibi Naruto (Kurama)"), "name": "Chibi Naruto (Kurama Mode)", "series": "Naruto",
        "element": "Spirit", "atk": 670, "def": 650},
    {"id": slugify("Chibi Madara (Ten Tails)"), "name": "Chibi Madara (Ten Tails)", "series": "Naruto",
        "element": "Dark", "atk": 680, "def": 620},
]