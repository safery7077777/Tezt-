import random

GAME_SPECS = {
    "tower": {
        "name": "Башня 🏰",
        "width": 5,
        "levels": 9,
        "mines_per_row": 1,
        "multipliers": {
            1: 1.2, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0, 6: 6.0, 7: 7.0, 8: 8.0, 9: 9.0
        }
    },
    "diamonds": {
        "name": "Алмазы 💎",
        "width": 3,
        "levels": 16,
        "mines_per_row": 1,
        "multipliers": {
            1: 1.4, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0, 6: 6.0, 7: 7.0, 8: 8.0, 9: 9.0,
            10: 10.0, 11: 11.0, 12: 12.0, 13: 13.0, 14: 14.0, 15: 15.0, 16: 16.0
        }
    },
    "pyramid": {
        "name": "Пирамида 🔺",
        "width": 4,
        "levels": 12,
        "mines_per_row": 1,
        "multipliers": {
            1: 1.3, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0, 6: 6.0, 7: 7.0, 8: 8.0, 9: 9.0,
            10: 10.0, 11: 11.0, 12: 12.0
        }
    }
}

def generate_mines(game_type: str) -> list:
    spec = GAME_SPECS[game_type]
    levels = spec["levels"]
    width = spec["width"]
    mines_count = spec["mines_per_row"]
    
    mines_list = []
    for _ in range(levels):
        mines = random.sample(range(width), mines_count)
        mines_list.append(mines)
    return mines_list
