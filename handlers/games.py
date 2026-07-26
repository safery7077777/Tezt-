import random
import re
import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from game_config import GAME_SPECS, generate_mines
from keyboards import get_game_keyboard, get_revealed_keyboard
from config import settings

logger = logging.getLogger(__name__)
router = Router()

def parse_bet(message: types.Message, bet_str: str) -> int:
    """Умный парсер ставки: поддерживает 'всё', '10к', '1.5кк', '2м'"""
    user_bal = db.get_balance(message.from_user.id)
    s = bet_str.strip().lower().replace(",", ".")

    # 1. Обработка Ва-банка
    if s in ["всё", "все", "all", "вабанк"]:
        if user_bal <= 0:
            raise ValueError("❌ Ваш баланс пуст!")
        return user_bal

    # 2. Обработка сокращений (к, кк, м)
    multiplier = 1
    if re.search(r'(кк|kk|м|m)$', s):
        multiplier = 1_000_000
        s = re.sub(r'(кк|kk|м|m)$', '', s)
    elif re.search(r'(к|k)$', s):
        multiplier = 1_000
        s = re.sub(r'(к|k)$', '', s)

    try:
        val = float(s)
        bet = int(val * multiplier)
    except ValueError:
        raise ValueError("❌ Неверный формат ставки! Используйте: `100`, `10к`, `1.5кк` или `всё`.")

    if bet <= 0:
        raise ValueError("❌ Ставка должна быть больше нуля.")
    
    if bet > user_bal:
        raise ValueError(f"❌ Недостаточно средств! Ваш баланс: **{user_bal:,}** коинов.")
    
    return bet

# === ГЕНЕРАЦИЯ КРАША ===
def generate_crash_multiplier() -> float:
    r = random.random()
    if r < 0.07: return 1.00
    elif r < 0.90: return round(1.01 + (random.random() ** 1.7) * 8.99, 2)
    else: return round(10.01 + (random.random() ** 2.0) * 90.0, 2)

# === ИГРА КРАШ ===
@router.message(Command("crash", "краш"))
async def cmd_crash(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/краш [ставка] [коэф]`\n_Примеры: /краш всё 2.5 или /краш 10к 1.5_", parse_mode="Markdown")
        return

    if db.get_active_game(message.from_user.id):
        await message.reply("❌ Сначала завершите текущую игру на поле!")
        return

    try:
        bet = parse_bet(message, parts[1])
        chosen_multiplier = float(parts[2].replace(",", "."))
        if chosen_multiplier <= 1.0: raise ValueError("❌ Коэффициент должен быть больше 1.0.")
    except ValueError as e:
        msg = str(e) if "❌" in str(e) else "❌ Ошибка в ставке или коэффициенте."
        await message.reply(msg, parse_mode="Markdown")
        return

    crash_point = generate_crash_multiplier()
    db.update_balance(message.from_user.id, -bet, is_game=True)
    db.increment_games_played(message.from_user.id)

    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    if crash_point >= chosen_multiplier:
        payout = int(bet * chosen_multiplier)
        new_bal = db.update_balance(message.from_user.id, payout, is_game=True)
        await message.reply(
            f"📈 **КРАШ**\n🚀 Ракета долетела до: **{crash_point:.2f}x**\n"
            f"🎉 Победитель: {user_mention}\n"
            f"🎯 Коэффициент: **{chosen_multiplier:.2f}x**\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}**", 
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id)
        await message.reply(
            f"📈 **КРАШ**\n💥 Ракету разорвало на: **{crash_point:.2f}x**\n"
            f"❌ Проигравший: {user_mention}\n"
            f"💸 Потеряно: **{bet:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}**", 
            parse_mode="Markdown"
        )

# === ИГРА ГОНКИ ===
@router.message(Command("race", "рейс"))
async def cmd_race(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Использование: `/race [ставка]` или `/рейс [ставка]`\n_Примеры: /race все, /рейс 10к_", parse_mode="Markdown")
        return

    try:
        bet = parse_bet(message, parts[1])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    animals = [
        ("🏎️ болид", 0),
        ("🐎 конь", 1),
        ("🐕 пёсель", 2),
        ("🐇 кролик", 3),
        ("🐢 черепаха", 4)
    ]

    builder = InlineKeyboardBuilder()
    for name, idx in animals:
        builder.row(types.InlineKeyboardButton(
            text=name,
            callback_data=f"race_choose:{idx}:{message.from_user.id}:{bet}"
        ))

    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    await message.reply(
        f"🏎️ **ГОНКИ**\n"
        f"👤 Игрок: {user_mention}\n"
        f"💰 Ставка: **{bet:,}** коинов\n\n"
        f"👉 **Выберите на кого ставите (Победа дает 10x):**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("race_choose:"))
async def handle_race_choice(callback: types.CallbackQuery):
    try:
        parts = callback.data.split(":")
        chosen_idx = int(parts[1])
        owner_id = int(parts[2])
        bet = int(parts[3])

        if callback.from_user.id != owner_id:
            await callback.answer("⚠️ Это не ваши гонки! Начните свои командой /race.", show_alert=True)
            return

        user_bal = db.get_balance(owner_id)
        if user_bal < bet:
            await callback.answer("❌ Недостаточно средств для совершения этой ставки!", show_alert=True)
            return

        # Моментально отвечаем на Callback во избежание зависания кнопки
        await callback.answer()

        # Снимаем ставку
        db.update_balance(owner_id, -bet, is_game=True)
        db.increment_games_played(owner_id)

        animals_emojis = {0: "🏎️", 1: "🐎", 2: "🐕", 3: "🐇", 4: "🐢"}
        animals_names = {0: "болид", 1: "конь", 2: "пёсель", 3: "кролик", 4: "черепаха"}

        positions = [0, 0, 0, 0, 0]
        track_length = 8

        user_mention = f"[{callback.from_user.full_name}](tg://user?id={callback.from_user.id})"

        # Анимация движения
        for step in range(4):
            for i in range(5):
                positions[i] += random.randint(1, 3)
                if positions[i] > track_length:
                    positions[i] = track_length

            track_text = []
            for i in range(5):
                emoji = animals_emojis[i]
                pos = positions[i]
                line = "➖" * pos + emoji + "➖" * (track_length - pos) + "🏁"
                chosen_mark = " 👈 ваш выбор" if i == chosen_idx else ""
                track_text.append(f"{line} {chosen_mark}")

            progress_msg = (
                f"🏎️ **ГОНКА НАЧАЛАСЬ!**\n"
                f"👤 Игрок: {user_mention}\n"
                f"💰 Ставка: **{bet:,}** коинов\n\n"
                + "\n".join(track_text)
            )

            try:
                await callback.message.edit_text(progress_msg, reply_markup=None, parse_mode="Markdown")
            except Exception:
                pass
            await asyncio.sleep(1.2)

        # Вычисляем победителя
        max_pos = max(positions)
        leaders = [i for i, pos in enumerate(positions) if pos == max_pos]
        winner_idx = random.choice(leaders)

        # Рисуем финальный финиш
        track_text = []
        for i in range(5):
            emoji = animals_emojis[i]
            pos = positions[i] if i != winner_idx else track_length
            if i == winner_idx:
                line = "➖" * track_length + "🏁" + emoji
            else:
                line = "➖" * pos + emoji + "➖" * (track_length - pos) + "🏁"
            chosen_mark = " 👈 ваш выбор" if i == chosen_idx else ""
            track_text.append(f"{line} {chosen_mark}")

        won = (chosen_idx == winner_idx)
        
        if won:
            payout = bet * 10
            new_bal = db.update_balance(owner_id, payout, is_game=True)
            result_text = (
                f"🏆 **ПОБЕДА!**\n"
                f"🎉 Первым финишировал {animals_emojis[winner_idx]} **{animals_names[winner_idx]}**!\n"
                f"💵 Ваш выигрыш (10x): **{payout:,}** коинов!\n"
                f"💰 Ваш баланс: **{new_bal:,}** коинов."
            )
        else:
            new_bal = db.get_balance(owner_id)
            result_text = (
                f"💥 **ПРОИГРЫШ!**\n"
                f"🏆 Победитель: {animals_emojis[winner_idx]} **{animals_names[winner_idx]}**\n"
                f"💸 Потеряно: **{bet:,}** коинов\n"
                f"💰 Ваш баланс: **{new_bal:,}** коинов."
            )

        final_msg = (
            f"🏎️ **ГОНКА ЗАВЕРШЕНА!**\n"
            f"👤 Игрок: {user_mention}\n\n"
            + "\n".join(track_text) + "\n\n"
            + result_text
        )

        try:
            await callback.message.edit_text(final_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка при выводе финиша гонки: {e}")

    except Exception as e:
        logger.exception(f"Критическая ошибка в обработчике гонок: {e}")
        try:
            await callback.answer("❌ Произошла ошибка при обработке игры.", show_alert=True)
        except Exception:
            pass


# === РУЛЕТКА ===
@router.message(Command("рулетка", "roulette"))
async def cmd_roulette(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/рулетка [ставка] [число/красное/черное/чет/нечет]`\n_Примеры: /рулетка 100 15, /рулетка все красное_", parse_mode="Markdown")
        return

    try:
        bet = parse_bet(message, parts[1])
        choice = parts[2].lower()
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    valid_choices = ["красное", "черное", "чет", "нечет"] + [str(i) for i in range(37)]
    if choice not in valid_choices:
        await message.reply("❌ Неверный выбор для рулетки. Выберите: `красное`, `черное`, `чет`, `нечет` или число от `0` до `36`.", parse_mode="Markdown")
        return

    db.update_balance(message.from_user.id, -bet, is_game=True)
    db.increment_games_played(message.from_user.id)

    roll = random.randint(0, 36)
    
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
    
    roll_color = "зеленое" if roll == 0 else ("красное" if roll in red_numbers else "черное")
    roll_parity = "чет" if roll != 0 and roll % 2 == 0 else ("нечет" if roll != 0 and roll % 2 != 0 else "")

    payout = 0
    win_message = ""
    won = False
    
    if choice == str(roll):
        payout = bet * 36
        win_message = f"✅ Выпало ваше число **{roll}**! Выигрыш **{payout:,}**."
        won = True
    elif choice == "красное" and roll_color == "красное":
        payout = bet * 2
        win_message = f"✅ Выпало **{roll_color}**! Выигрыш **{payout:,}**."
        won = True
    elif choice == "черное" and roll_color == "черное":
        payout = bet * 2
        win_message = f"✅ Выпало **{roll_color}**! Выигрыш **{payout:,}**."
        won = True
    elif choice == "чет" and roll_parity == "чет":
        payout = bet * 2
        win_message = f"✅ Выпало **четное**! Выигрыш **{payout:,}**."
        won = True
    elif choice == "нечет" and roll_parity == "нечет":
        payout = bet * 2
        win_message = f"✅ Выпало **нечетное**! Выигрыш **{payout:,}**."
        won = True

    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    if won:
        new_bal = db.update_balance(message.from_user.id, payout, is_game=True)
        await message.reply(
            f"🎰 **РУЛЕТКА**\n"
            f"👤 Игрок: {user_mention}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice}`\n"
            f"🎲 Результат: **{roll}** ({roll_color}, {roll_parity if roll_parity else 'Зиро'})\n"
            f"{win_message}\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id)
        await message.reply(
            f"🎰 **РУЛЕТКА**\n"
            f"👤 Игрок: {user_mention}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice}`\n"
            f"🎲 Результат: **{roll}** ({roll_color}, {roll_parity if roll_parity else 'Зиро'})\n"
            f"❌ Вы проиграли.\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )

# === УГАДАЙ ЧИСЛО ===
@router.message(Command("guess", "угадай"))
async def cmd_guess(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/guess [ставка] [число] [диапазон (опц. 100 или 1000)]`\n_Примеры: /guess 100 50, /guess все 500 1000_", parse_mode="Markdown")
        return

    try:
        bet = parse_bet(message, parts[1])
        user_guess = int(parts[2])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    max_range = 100
    if len(parts) > 3 and parts[3].isdigit():
        max_range = int(parts[3])
    
    if max_range not in [100, 1000]:
        await message.reply("❌ Доступные диапазоны: `1-100` (погрешность ±10) или `1-1000` (погрешность ±100).", parse_mode="Markdown")
        return

    if not (1 <= user_guess <= max_range):
        await message.reply(f"❌ Ваше число должно быть в диапазоне от `1` до `{max_range}`.", parse_mode="Markdown")
        return

    tolerance = 100 if max_range == 1000 else 10
    
    db.update_balance(message.from_user.id, -bet, is_game=True)
    db.increment_games_played(message.from_user.id)

    bot_number = random.randint(1, max_range)
    payout = 0
    result_msg = ""
    won = False

    if user_guess == bot_number:
        payout = bet * 10
        result_msg = f"🎉 **БИНГО!** Вы угадали число **{bot_number}**!"
        won = True
    elif abs(user_guess - bot_number) <= tolerance:
        payout = bet
        result_msg = f"↔️ Очень близко! Число было **{bot_number}**. Вы получаете возврат ставки."
        won = True
    else:
        result_msg = f"❌ Мимо. Число было **{bot_number}**."

    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    if won:
        new_bal = db.update_balance(message.from_user.id, payout, is_game=True)
        await message.reply(
            f"🔢 **УГАДАЙ ЧИСЛО**\n"
            f"👤 Игрок: {user_mention}\n"
            f"💸 Ваша ставка: **{bet:,}** на число **{user_guess}** (в диапазоне 1-{max_range})\n"
            f"🎲 Загаданное число: **{bot_number}**\n"
            f"{result_msg}\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id)
        await message.reply(
            f"🔢 **УГАДАЙ ЧИСЛО**\n"
            f"👤 Игрок: {user_mention}\n"
            f"💸 Ваша ставка: **{bet:,}** на число **{user_guess}** (в диапазоне 1-{max_range})\n"
            f"🎲 Загаданное число: **{bot_number}**\n"
            f"{result_msg}\n"
            f"💸 Потеряно: **{bet:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )

# === КУБИКИ ===
@router.message(Command("кубик", "dice"))
async def cmd_dice(message: types.Message):
    parts = message.text.split()
    if len(parts) < 4:
        await message.reply("📝 Использование: `/кубик [1/2] [меньше/больше/число] [ставка]`\n_Примеры: /кубик 1 меньше 100, /кубик 2 7 все_", parse_mode="Markdown")
        return

    try:
        num_dice = int(parts[1])
        if num_dice not in [1, 2]:
            raise ValueError("❌ Выберите `1` или `2` кубика.")
        
        choice_str = parts[2].lower()
        bet = parse_bet(message, parts[3])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    valid_choices = ["меньше", "больше", "3"] if num_dice == 1 else ["меньше", "больше", "7"]
    if choice_str not in valid_choices:
        if num_dice == 1:
            await message.reply("❌ Для 1 кубика выберите: `меньше`, `больше` или `3`.", parse_mode="Markdown")
        else:
            await message.reply("❌ Для 2 кубиков выберите: `меньше`, `больше` или `7`.", parse_mode="Markdown")
        return

    db.update_balance(message.from_user.id, -bet, is_game=True)
    db.increment_games_played(message.from_user.id)

    rolls = [random.randint(1, 6) for _ in range(num_dice)]
    total_roll = sum(rolls)
    
    payout = 0
    result_msg = ""
    won = False

    if num_dice == 1:
        if choice_str == "меньше" and total_roll < 3:
            payout = bet * 2
            result_msg = "✅ Выпало меньше 3!"
            won = True
        elif choice_str == "больше" and total_roll > 3:
            payout = bet * 2
            result_msg = "✅ Выпало больше 3!"
            won = True
        elif choice_str == "3" and total_roll == 3:
            payout = bet * 2
            result_msg = "✅ Выпало ровно 3!"
            won = True
    elif num_dice == 2:
        if choice_str == "меньше" and total_roll < 7:
            payout = bet * 2
            result_msg = "✅ Выпало меньше 7!"
            won = True
        elif choice_str == "больше" and total_roll > 7:
            payout = bet * 2
            result_msg = "✅ Выпало больше 7!"
            won = True
        elif choice_str == "7" and total_roll == 7:
            payout = bet * 2
            result_msg = "✅ Выпало ровно 7!"
            won = True

    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    if won:
        new_bal = db.update_balance(message.from_user.id, payout, is_game=True)
        await message.reply(
            f"🎲 **КУБИКИ ({num_dice} шт.)**\n"
            f"👤 Игрок: {user_mention}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice_str}`\n"
            f"🔮 Результат: {' + '.join(map(str, rolls))} = **{total_roll}**\n"
            f"{result_msg}\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id)
        await message.reply(
            f"🎲 **КУБИКИ ({num_dice} шт.)**\n"
            f"👤 Игрок: {user_mention}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice_str}`\n"
            f"🔮 Результат: {' + '.join(map(str, rolls))} = **{total_roll}**\n"
            f"❌ Вы проиграли.\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )


# === ЗАПУСК ИГР НА ПОЛЕ ===
@router.message(Command("tower", "diamonds", "pyramid", "башня", "алмазы", "пирамида"))
async def start_grid_game(message: types.Message):
    cmd = message.text.split()[0].lower().replace("/", "")
    if cmd in ["башня", "tower"]: game_type = "tower"
    elif cmd in ["алмазы", "diamonds"]: game_type = "diamonds"
    else: game_type = "pyramid"

    if db.get_active_game(message.from_user.id):
        await message.reply("❌ У вас уже есть активная игра! Закончите её.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(f"📝 Использование: `/{cmd} [ставка]`\n_Примеры: /{cmd} 500, /{cmd} 10к, /{cmd} всё_", parse_mode="Markdown")
        return

    try:
        bet = parse_bet(message, parts[1])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    spec = GAME_SPECS[game_type]
    db.start_game(message.from_user.id, game_type, bet, generate_mines(game_type))
    db.increment_games_played(message.from_user.id)
    
    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    kb = get_game_keyboard(1, {}, spec["levels"], spec["width"], message.from_user.id)
    await message.reply(
        f"🎮 **{spec['name']}**\n👤 Игрок: {user_mention}\n"
        f"💰 Ставка: **{bet:,}** коинов\n📈 Множитель: **1.0x**\n\n"
        f"👇 Выберите ячейку в нижнем ряду:", 
        reply_markup=kb, parse_mode="Markdown"
    )

# === CALLBACK HANDLER (ХОДЫ И КНОПКИ) ===
@router.callback_query(F.data.startswith("game_action:"))
async def handle_game_callback(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    action = parts[1]
    owner_id = int(parts[-1])

    if owner_id != 0 and owner_id != callback.from_user.id:
        await callback.answer("⚠️ Это не ваша игра! Начните свою.", show_alert=True)
        return

    user_id = callback.from_user.id
    game = db.get_active_game(user_id)
    if not game:
        await callback.answer("❌ Игра не найдена.")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    spec = GAME_SPECS[game["type"]]
    user_mention = f"[{callback.from_user.full_name}](tg://user?id={callback.from_user.id})"

    if action == "cashout":
        multiplier = game['multiplier']
        payout = db.finish_game(user_id, won=True)
        await callback.message.edit_text(
            f"🎉 **ВЫИГРЫШ ЗАБРАН!**\n👤 {user_mention}\n"
            f"📈 Итоговый коэф: **{multiplier}x**\n"
            f"💵 Сумма: **{payout:,}** коинов\n💰 Баланс: **{db.get_balance(user_id):,}**",
            reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"]),
            parse_mode="Markdown"
        )
        return

    if action == "forfeit":
        bet = game['bet']
        db.finish_game(user_id, won=False)
        await callback.message.edit_text(
            f"❌ **ИГРА ОКОНЧЕНА (СДАЧА)**\n👤 {user_mention}\n"
            f"💸 Потеряно: **{bet:,}** коинов.",
            reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"]),
            parse_mode="Markdown"
        )
        return

    if action == "click":
        lvl, col = int(parts[2]), int(parts[3])
        if lvl != game["current_level"]:
            await callback.answer("⚠️ Делайте ход на активном ряду!", show_alert=True)
            return

        if col in game["mines"][lvl-1]:
            bet = game['bet']
            db.finish_game(user_id, won=False)
            await callback.message.edit_text(
                f"💥 **БУМ! МИНА!**\n👤 {user_mention}\n"
                f"💀 Вы взорвались на {lvl} ряду.\n💸 Потеряно: **{bet:,}** коинов.",
                reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"], lvl, col),
                parse_mode="Markdown"
            )
        else:
            history = game["history"]
            history[str(lvl)] = col
            completed_mult = spec["multipliers"][lvl]
            
            if lvl == spec["levels"]:
                db.update_game_level(user_id, lvl+1, completed_mult, history)
                payout = db.finish_game(user_id, won=True)
                await callback.message.edit_text(
                    f"🏆 **ПОЛНАЯ ПОБЕДА!**\n👤 {user_mention}\n"
                    f"📈 Множитель: **{completed_mult}x**\n"
                    f"💵 Выигрыш: **{payout:,}** коинов!",
                    reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], history),
                    parse_mode="Markdown"
                )
            else:
                db.update_game_level(user_id, lvl+1, completed_mult, history)
                await callback.message.edit_reply_markup(
                    reply_markup=get_game_keyboard(lvl+1, history, spec["levels"], spec["width"], user_id)
                )
        await callback.answer()
