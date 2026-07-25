import random
import re
from aiogram import Router, types, F
from aiogram.filters import Command
from database import db
from game_config import GAME_SPECS, generate_mines
from keyboards import get_game_keyboard, get_revealed_keyboard
from config import settings

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
    # Миллионы (кк, kk, м, m)
    if re.search(r'(кк|kk|м|m)$', s):
        multiplier = 1_000_000
        s = re.sub(r'(кк|kk|м|m)$', '', s)
    # Тысячи (к, k)
    elif re.search(r'(к|k)$', s):
        multiplier = 1_000
        s = re.sub(r'(к|k)$', '', s)

    try:
        # Превращаем в число (float, чтобы работало 1.5к)
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
    db.update_balance(message.from_user.id, -bet) # Снятие ставки
    db.increment_games_played(message.from_user.id) # Игра сыграна

    if crash_point >= chosen_multiplier:
        payout = int(bet * chosen_multiplier)
        new_bal = db.update_balance(message.from_user.id, payout) # Начисление выигрыша
        await message.reply(
            f"📈 **КРАШ**\n🚀 Ракета долетела до: **{crash_point:.2f}x**\n"
            f"🎉 Победитель: {message.from_user.mention_markdown()}\n"
            f"🎯 Коэффициент: **{chosen_multiplier:.2f}x**\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}**", 
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id) # Баланс уже без ставки
        await message.reply(
            f"📈 **КРАШ**\n💥 Ракету разорвало на: **{crash_point:.2f}x**\n"
            f"❌ Проигравший: {message.from_user.mention_markdown()}\n"
            f"💸 Потеряно: **{bet:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}**", 
            parse_mode="Markdown"
        )

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

    # Валидация выбора рулетки
    valid_choices = ["красное", "черное", "чет", "нечет"] + [str(i) for i in range(37)] # 0-36
    if choice not in valid_choices:
        await message.reply("❌ Неверный выбор для рулетки. Выберите: `красное`, `черное`, `чет`, `нечет` или число от `0` до `36`.", parse_mode="Markdown")
        return

    db.update_balance(message.from_user.id, -bet) # Снятие ставки
    db.increment_games_played(message.from_user.id) # Игра сыграна

    # Генерируем результат рулетки
    roll = random.randint(0, 36)
    
    # Определяем цвет
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
    
    roll_color = ""
    if roll == 0:
        roll_color = "зеленое" # Зиро
    elif roll in red_numbers:
        roll_color = "красное"
    elif roll in black_numbers:
        roll_color = "черное"
    
    roll_parity = "чет" if roll != 0 and roll % 2 == 0 else ("нечет" if roll != 0 and roll % 2 != 0 else "")

    payout = 0
    win_message = ""
    
    # Проверка выигрыша
    won = False
    if choice == str(roll): # Ставка на число
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

    if won:
        new_bal = db.update_balance(message.from_user.id, payout)
        await message.reply(
            f"🎰 **РУЛЕТКА**\n"
            f"👤 Игрок: {message.from_user.mention_markdown()}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice}`\n"
            f"🎲 Результат: **{roll}** ({roll_color}, {roll_parity if roll_parity else 'Зиро'})\n"
            f"{win_message}\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id) # Баланс уже без ставки
        await message.reply(
            f"🎰 **РУЛЕТКА**\n"
            f"👤 Игрок: {message.from_user.mention_markdown()}\n"
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
        await message.reply("📝 Использование: `/guess [ставка] [число (1-100/1000)] [макс_диапазон (опц.)]`\n_Примеры: /guess 100 50, /guess все 500 1000_", parse_mode="Markdown")
        return

    try:
        bet = parse_bet(message, parts[1])
        user_guess = int(parts[2])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    max_range = 100 # По умолчанию
    if len(parts) > 3 and parts[3].isdigit():
        max_range = int(parts[3])
    
    if max_range not in [100, 1000]:
        await message.reply("❌ Доступные диапазоны: `1-100` (погрешность ±10) или `1-1000` (погрешность ±100).", parse_mode="Markdown")
        return

    if not (1 <= user_guess <= max_range):
        await message.reply(f"❌ Ваше число должно быть в диапазоне от `1` до `{max_range}`.", parse_mode="Markdown")
        return

    tolerance = 100 if max_range == 1000 else 10
    
    db.update_balance(message.from_user.id, -bet) # Снятие ставки
    db.increment_games_played(message.from_user.id) # Игра сыграна

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

    if won:
        new_bal = db.update_balance(message.from_user.id, payout)
        await message.reply(
            f"🔢 **УГАДАЙ ЧИСЛО**\n"
            f"👤 Игрок: {message.from_user.mention_markdown()}\n"
            f"💸 Ваша ставка: **{bet:,}** на число **{user_guess}** (в диапазоне 1-{max_range})\n"
            f"🎲 Загаданное число: **{bot_number}**\n"
            f"{result_msg}\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id) # Баланс уже без ставки
        await message.reply(
            f"🔢 **УГАДАЙ ЧИСЛО**\n"
            f"👤 Игрок: {message.from_user.mention_markdown()}\n"
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

    # Валидация выбора для кубиков
    valid_choices = []
    if num_dice == 1:
        valid_choices = ["меньше", "больше", "3"]
    elif num_dice == 2:
        valid_choices = ["меньше", "больше", "7"]
    
    if choice_str not in valid_choices:
        if num_dice == 1:
            await message.reply("❌ Для 1 кубика выберите: `меньше`, `больше` или `3`.", parse_mode="Markdown")
        else: # num_dice == 2
            await message.reply("❌ Для 2 кубиков выберите: `меньше`, `больше` или `7`.", parse_mode="Markdown")
        return

    db.update_balance(message.from_user.id, -bet) # Снятие ставки
    db.increment_games_played(message.from_user.id) # Игра сыграна

    # Бросаем кубики
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

    if won:
        new_bal = db.update_balance(message.from_user.id, payout)
        await message.reply(
            f"🎲 **КУБИКИ ({num_dice} шт.)**\n"
            f"👤 Игрок: {message.from_user.mention_markdown()}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice_str}`\n"
            f"🔮 Результат: {' + '.join(map(str, rolls))} = **{total_roll}**\n"
            f"{result_msg}\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        new_bal = db.get_balance(message.from_user.id) # Баланс уже без ставки
        await message.reply(
            f"🎲 **КУБИКИ ({num_dice} шт.)**\n"
            f"👤 Игрок: {message.from_user.mention_markdown()}\n"
            f"💸 Ваша ставка: **{bet:,}** на `{choice_str}`\n"
            f"🔮 Результат: {' + '.join(map(str, rolls))} = **{total_roll}**\n"
            f"❌ Вы проиграли.\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )


# === ЗАПУСК ИГР НА ПОЛЕ ===
@router.message(Command("tower", "diamonds", "pyramid", "башня", "алмазы", "пирамида"))
async def start_grid_game(message: types.Message):
    # Определяем тип игры по команде
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
    db.increment_games_played(message.from_user.id) # Игра сыграна (пошаговая)
    
    kb = get_game_keyboard(1, {}, spec["levels"], spec["width"], message.from_user.id)
    await message.reply(
        f"🎮 **{spec['name']}**\n👤 Игрок: {message.from_user.mention_markdown()}\n"
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

    # Защита от чужих нажатий
    if owner_id != 0 and owner_id != callback.from_user.id:
        await callback.answer("⚠️ Это не ваша игра! Начните свою.", show_alert=True)
        return

    user_id = callback.from_user.id
    game = db.get_active_game(user_id)
    if not game:
        await callback.answer("❌ Игра не найдена.")
        try: # Попытаться удалить старую клавиатуру, если игра уже завершена по тайм-ауту/сбою
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass # Если не удалось удалить, игнорируем
        return

    spec = GAME_SPECS[game["type"]]

    if action == "cashout":
        multiplier = game['multiplier']
        payout = db.finish_game(user_id, won=True)
        await callback.message.edit_text(
            f"🎉 **ВЫИГРЫШ ЗАБРАН!**\n👤 {callback.from_user.mention_markdown()}\n"
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
            f"❌ **ИГРА ОКОНЧЕНА (СДАЧА)**\n👤 {callback.from_user.mention_markdown()}\n"
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
                f"💥 **БУМ! МИНА!**\n👤 {callback.from_user.mention_markdown()}\n"
                f"💀 Вы взорвались на {lvl} ряду.\n💸 Потеряно: **{bet:,}** коинов.",
                reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"], lvl, col),
                parse_mode="Markdown"
            )
        else:
            history = game["history"]
            history[str(lvl)] = col
            completed_mult = spec["multipliers"][lvl] # Множитель за ПРОЙДЕННЫЙ уровень
            
            if lvl == spec["levels"]: # Пройден последний уровень
                db.update_game_level(user_id, lvl+1, completed_mult, history) # Обновляем на последний множитель
                payout = db.finish_game(user_id, won=True)
                await callback.message.edit_text(
                    f"🏆 **ПОЛНАЯ ПОБЕДА!**\n👤 {callback.from_user.mention_markdown()}\n"
                    f"📈 Итоговый множитель: **{completed_mult}x**\n"
                    f"💵 Выигрыш: **{payout:,}** коинов!",
                    reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], history),
                    parse_mode="Markdown"
                )
            else:
                db.update_game_level(user_id, lvl+1, completed_mult, history) # Обновляем текущий уровень и множитель
                await callback.message.edit_reply_markup(
                    reply_markup=get_game_keyboard(lvl+1, history, spec["levels"], spec["width"], user_id)
                )
        await callback.answer()
