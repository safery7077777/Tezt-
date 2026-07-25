from aiogram import Router, types
from aiogram.filters import Command
from config import ADMIN_ID_LIST, ADMIN_USERNAME_LIST
from database import db
from game_config import GAME_SPECS

router = Router()

def is_admin(user: types.User) -> bool:
    if user.id in ADMIN_ID_LIST:
        return True
    if user.username and user.username.lower() in ADMIN_USERNAME_LIST:
        return True
    return False

# === ВЫДАЧА КОИНОВ ===
@router.message(Command("выдать", "give"))
async def admin_give_coins(message: types.Message):
    if not is_admin(message.from_user):
        await message.reply("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/выдать [юзернейм_или_ID] [количество]`", parse_mode="Markdown")
        return

    target_input = parts[1].strip()
    amount_str = parts[2].strip()

    if not amount_str.isdigit():
        await message.reply("❌ Количество коинов должно быть целым числом.")
        return

    amount = int(amount_str)
    if amount <= 0:
        await message.reply("❌ Количество коинов должно быть больше нуля.")
        return

    target_uid, user_data = db.get_user_by_username(target_input)
    if not target_uid:
        await message.reply(
            f"❌ Игрок `{target_input}` не найден в базе данных.\nОн должен написать боту хотя бы один раз.",
            parse_mode="Markdown"
        )
        return

    new_bal = db.update_balance(int(target_uid), amount)
    await message.reply(
        f"✅ Выдано **{amount:,}** коинов пользователю `{target_input}`.\n"
        f"💰 Новый баланс пользователя: **{new_bal:,}** коинов.",
        parse_mode="Markdown"
    )

# === СПИСАНИЕ (ЗАБРАТЬ) КОИНОВ ===
@router.message(Command("забрать", "take"))
async def admin_take_coins(message: types.Message):
    if not is_admin(message.from_user):
        await message.reply("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/забрать [юзернейм_или_ID] [количество]`", parse_mode="Markdown")
        return

    target_input = parts[1].strip()
    amount_str = parts[2].strip()

    if not amount_str.isdigit():
        await message.reply("❌ Количество коинов должно быть целым положительным числом.")
        return

    amount = int(amount_str)
    if amount <= 0:
        await message.reply("❌ Количество коинов должно быть больше нуля.")
        return

    target_uid, user_data = db.get_user_by_username(target_input)
    if not target_uid:
        await message.reply(
            f"❌ Игрок `{target_input}` не найден в базе данных.\nОн должен написать боту хотя бы один раз.",
            parse_mode="Markdown"
        )
        return

    # Передаем отрицательное значение для уменьшения баланса
    new_bal = db.update_balance(int(target_uid), -amount)
    await message.reply(
        f"🔻 Списано **{amount:,}** коинов у пользователя `{target_input}`.\n"
        f"💰 Новый баланс пользователя: **{new_bal:,}** коинов.",
        parse_mode="Markdown"
    )

# === РЕЖИМ БОГА: ПРОСМОТР АКТИВНОЙ ИГРЫ ===
@router.message(Command("просмотр", "view"))
async def admin_view_game(message: types.Message):
    if not is_admin(message.from_user):
        await message.reply("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()
    
    if len(parts) < 2:
        target_uid = str(message.from_user.id)
        target_input = "Ваша собственная игра"
    else:
        target_input = parts[1].strip()
        found_uid, user_data = db.get_user_by_username(target_input)
        if not found_uid:
            await message.reply(
                f"❌ Пользователь `{target_input}` не найден в базе данных.",
                parse_mode="Markdown"
            )
            return
        target_uid = found_uid

    game = db.get_active_game(int(target_uid))
    if not game:
        if len(parts) < 2:
            await message.reply(
                "👀 У вас сейчас **нет активных пошаговых игр**.\n"
                "Эта команда работает только для игр типа **Башня, Алмазы, Пирамида**."
            )
        else:
            await message.reply(
                f"👀 У пользователя `{target_input}` сейчас **нет активных пошаговых игр**.",
                parse_mode="Markdown"
            )
        return

    # Эта команда работает только для игр на поле (Башня, Алмазы, Пирамида)
    if game["type"] not in ["tower", "diamonds", "pyramid"]:
        await message.reply(
            f"👀 Игра пользователя `{target_input}` ({game['type']}) не является пошаговой и не может быть просмотрена.",
            parse_mode="Markdown"
        )
        return

    game_type = game["type"]
    spec = GAME_SPECS[game_type]
    bet = game["bet"]
    current_level = game["current_level"]
    history = game.get("history", {})
    mines_layout = game["mines"]

    grid_lines = []
    for lvl in range(spec["levels"], 0, -1):
        row_mines = mines_layout[lvl - 1]
        player_pick = history.get(str(lvl))
        
        row_emojis = []
        for col in range(spec["width"]):
            is_mine = col in row_mines
            is_picked = player_pick is not None and int(player_pick) == col
            
            if is_mine:
                row_emojis.append("💣")
            elif is_picked:
                row_emojis.append("🟢")
            else:
                row_emojis.append("⚪")

        row_str = " ".join(row_emojis)
        mult = spec["multipliers"][lvl]
        marker = " 👈 (сейчас выбирать тут)" if lvl == current_level else ""
        
        grid_lines.append(f"**Ряд {lvl:02d}** ({mult}x):  {row_str}{marker}")

    response = [
        f"🕵️‍♂️ **РЕЖИМ НАБЛЮДАТЕЛЯ**",
        f"👤 Цель: **{target_input}**",
        f"🎮 Игра: **{spec['name']}**",
        f"💵 Ставка: **{bet:,}** коинов",
        f"📈 Текущий уровень: **{current_level}** из **{spec['levels']}**",
        f"📊 Накопленный множитель: **{game['multiplier']}x**\n",
        "🗺 **КАРТА ИГРОВОГО ПОЛЯ (Сверху вниз):**",
        "ℹ️ _💣 — Мина | 🟢 — Выбрано вами | ⚪ — Безопасно_\n",
        "\n".join(grid_lines)
    ]

    await message.reply("\n".join(response), parse_mode="Markdown")
