import random

GAME_SPECS = {
    "tower": {
        "name": "Башня 🏰",
        "width": 5,
        "levels": 9,
        "mines_per_row": 1,
        "multipliers": {
            1: 1.21,
            2: 1.52,
            3: 1.88,
            4: 2.37,
            5: 2.96,
            6: 3.70,
            7: 4.63,
            8: 5.78,
            9: 7.23
        }
    },
    "diamonds": {
        "name": "Алмазы 💎",
        "width": 3,
        "levels": 16,
        "mines_per_row": 1,
        "multipliers": {
            1: 1.46,
            2: 2.18,
            3: 3.27,
            4: 4.91,
            5: 7.37,
            6: 11.05,
            7: 16.57,
            8: 24.86,
            9: 37.29,
            10: 55.94,
            11: 83.90,
            12: 125.85,
            13: 188.78,
            14: 283.17,
            15: 424.76,
            16: 637.14
        }
    },
    "pyramid": {
        "name": "Пирамида 🔺",
        "width": 4,
        "levels": 12,
        "mines_per_row": 1,
        "multipliers": {
            1: 1.31,
            2: 1.74,
            3: 2.32,
            4: 3.10,
            5: 4.13,
            6: 5.51,
            7: 7.34,
            8: 9.79,    # Восстановленный 8-й уровень
            9: 13.05,   # Корректный 9-й уровень
            10: 17.40,  # Корректный 10-й уровень
            11: 23.20,  # Корректный 11-й уровень
            12: 30.94   # Корректный 12-й уровень
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
