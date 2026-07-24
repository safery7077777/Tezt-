from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_game_keyboard(current_level: int, history: dict, max_levels: int, width: int, owner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Строим уровни сверху вниз
    for lvl in range(max_levels, 0, -1):
        row_buttons = []
        for col in range(width):
            if lvl > current_level:
                # В префикс добавляем ID владельца
                row_buttons.append(
                    InlineKeyboardButton(text="🔒", callback_data=f"game_action:locked:{owner_id}")
                )
            elif lvl == current_level:
                row_buttons.append(
                    InlineKeyboardButton(text="❓", callback_data=f"game_action:click:{lvl}:{col}:{owner_id}")
                )
            else:
                picked_col = history.get(str(lvl))
                if picked_col is not None and col == int(picked_col):
                    row_buttons.append(
                        InlineKeyboardButton(text="💎", callback_data=f"game_action:passed:{owner_id}")
                    )
                else:
                    row_buttons.append(
                        InlineKeyboardButton(text="▫️", callback_data=f"game_action:passed:{owner_id}")
                    )
        builder.row(*row_buttons)
        
    if current_level > 1:
        builder.row(
            InlineKeyboardButton(text="📥 Забрать выигрыш", callback_data=f"game_action:cashout:{owner_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="❌ Сдаться", callback_data=f"game_action:forfeit:{owner_id}")
        )
        
    return builder.as_markup()

def get_revealed_keyboard(max_levels: int, width: int, mines: list, history: dict, exploded_lvl: int = -1, exploded_col: int = -1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Для завершенной игры OWNER_ID уже не важен, ставим 0
    for lvl in range(max_levels, 0, -1):
        row_buttons = []
        row_mines = mines[lvl - 1]
        for col in range(width):
            if lvl == exploded_lvl and col == exploded_col:
                row_buttons.append(InlineKeyboardButton(text="💥", callback_data="game_action:ended:0"))
            elif col in row_mines:
                row_buttons.append(InlineKeyboardButton(text="💣", callback_data="game_action:ended:0"))
            else:
                picked_col = history.get(str(lvl))
                if picked_col is not None and col == int(picked_col):
                    row_buttons.append(InlineKeyboardButton(text="💎", callback_data="game_action:ended:0"))
                else:
                    row_buttons.append(InlineKeyboardButton(text="▫️", callback_data="game_action:ended:0"))
        builder.row(*row_buttons)
    return builder.as_markup()
