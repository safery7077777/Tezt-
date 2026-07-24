from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_game_keyboard(current_level: int, history: dict, max_levels: int, width: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Строим уровни сверху вниз (с последнего до первого)
    for lvl in range(max_levels, 0, -1):
        row_buttons = []
        for col in range(width):
            if lvl > current_level:
                # Закрытый верхний уровень
                row_buttons.append(
                    InlineKeyboardButton(text="🔒", callback_data="game_action:locked")
                )
            elif lvl == current_level:
                # Текущий уровень, доступный для хода
                row_buttons.append(
                    InlineKeyboardButton(text="❓", callback_data=f"game_action:click:{lvl}:{col}")
                )
            else:
                # Пройденный нижний уровень
                picked_col = history.get(str(lvl))
                if picked_col is not None and col == int(picked_col):
                    row_buttons.append(
                        InlineKeyboardButton(text="💎", callback_data="game_action:passed")
                    )
                else:
                    row_buttons.append(
                        InlineKeyboardButton(text="▫️", callback_data="game_action:passed")
                    )
        builder.row(*row_buttons)
        
    # Кнопка досрочного вывода (если пройден хотя бы 1 уровень)
    if current_level > 1:
        builder.row(
            InlineKeyboardButton(text="📥 Забрать выигрыш", callback_data="game_action:cashout")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="❌ Сдаться (потеря ставки)", callback_data="game_action:forfeit")
        )
        
    return builder.as_markup()

def get_revealed_keyboard(max_levels: int, width: int, mines: list, history: dict, exploded_lvl: int = -1, exploded_col: int = -1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lvl in range(max_levels, 0, -1):
        row_buttons = []
        row_mines = mines[lvl - 1]
        for col in range(width):
            if lvl == exploded_lvl and col == exploded_col:
                row_buttons.append(InlineKeyboardButton(text="💥", callback_data="game_action:ended"))
            elif col in row_mines:
                row_buttons.append(InlineKeyboardButton(text="💣", callback_data="game_action:ended"))
            else:
                picked_col = history.get(str(lvl))
                if picked_col is not None and col == int(picked_col):
                    row_buttons.append(InlineKeyboardButton(text="💎", callback_data="game_action:ended"))
                else:
                    row_buttons.append(InlineKeyboardButton(text="▫️", callback_data="game_action:ended"))
        builder.row(*row_buttons)
    return builder.as_markup()
