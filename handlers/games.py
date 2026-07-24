import random
from aiogram import Router, types, F
from aiogram.filters import Command
from database import db
from game_config import GAME_SPECS, generate_mines
from keyboards import get_game_keyboard, get_revealed_keyboard
from config import settings

router = Router()

def parse_bet(message: types.Message, bet_str: str) -> int:
    if not bet_str.isdigit():
        raise ValueError("❌ Ставка должна быть целым положительным числом.")
    bet = int(bet_str)
    if bet <= 0:
        raise ValueError("❌ Ставка должна быть больше нуля.")
    
    user_bal = db.get_balance(message.from_user.id)
    if bet > user_bal:
        raise ValueError(f"❌ Недостаточно средств! Ваш баланс: **{user_bal:,}** коинов.")
    
    return bet

# === ГЕНЕРАЦИЯ КРАША (НОВАЯ МАТЕМАТИКА) ===
def generate_crash_multiplier() -> float:
    r = random.random()
    if r < 0.07:  
        # 7% шанс моментального взрыва на взлете
        return 1.00
    elif r < 0.90:  
        # 83% шанс взрыва в диапазоне 1.01x - 10.0x
        # Возведение в степень 1.7 сдвигает вероятность к началу (низкие иксы выпадают чаще)
        return round(1.01 + (random.random() ** 1.7) * 8.99, 2)
    else:  
        # 10% шанс улететь выше 10.0x (редкие крупные множители)
        return round(10.01 + (random.random() ** 2.0) * 90.0, 2)

# === ИГРА КРАШ ===
@router.message(Command("crash", "краш"))
async def cmd_crash(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/crash [ставка] [коэффициент]`\n_Пример: /crash 100 2.5_", parse_mode="Markdown")
        return

    active_game = db.get_active_game(message.from_user.id)
    if active_game:
        await message.reply("❌ Нельзя играть в Краш при активной игре на поле (Башня/Алмазы/Пирамида)!")
        return

    try:
        bet = parse_bet(message, parts[1])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    coef_str = parts[2].replace(",", ".")
    try:
        chosen_multiplier = float(coef_str)
        if chosen_multiplier <= 1.0:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Коэффициент автовывода должен быть числом больше 1.0.")
        return

    # Генерируем точку краша ракеты
    crash_point = generate_crash_multiplier()

    # Списываем ставку перед началом полета
    db.update_balance(message.from_user.id, -bet)

    # Логика исхода игры
    if crash_point >= chosen_multiplier:
        # Ракета долетела до коэффициента игрока -> Победа!
        payout = int(bet * chosen_multiplier)
        new_bal = db.update_balance(message.from_user.id, payout)
        
        await message.reply(
            f"📈 **ИГРА КРАШ**\n\n"
            f"🚀 Ракета успешно долетела до вашего автовывода и полетела дальше!\n"
            f"💥 Ракета взорвалась на отметке: **{crash_point:.2f}x**\n\n"
            f"🎉 **ВЫ ВЫИГРАЛИ!**\n"
            f"🎯 Ваша цель: **{chosen_multiplier:.2f}x**\n"
            f"💵 Начислено: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )
    else:
        # Ракета взорвалась раньше -> Проигрыш
        new_bal = db.get_balance(message.from_user.id)
        
        await message.reply(
            f"📈 **ИГРА КРАШ**\n\n"
            f"💥 **РАКЕТА КРАШНУЛАСЬ!**\n"
            f"💨 Взрыв произошел на отметке: **{crash_point:.2f}x**\n\n"
            f"❌ **ВЫ ПРОИГРАЛИ!**\n"
            f"🎯 Ваша цель была: **{chosen_multiplier:.2f}x**\n"
            f"💸 Потеряно: **{bet:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}** коинов.",
            parse_mode="Markdown"
        )

# === ЗАПУСК ИГР НА ПОЛЕ ===
@router.message(Command("tower", "diamonds", "pyramid", "башня", "алмазы", "пирамида"))
async def start_grid_game(message: types.Message):
    cmd = message.text.split()[0].lower().replace("/", "")
    if cmd in ["башня", "tower"]:
        game_type = "tower"
    elif cmd in ["алмазы", "diamonds"]:
        game_type = "diamonds"
    else:
        game_type = "pyramid"

    db.get_user(message.from_user.id, message.from_user.username)
    
    active = db.get_active_game(message.from_user.id)
    if active:
        await message.reply(f"❌ У вас уже запущена игра **{GAME_SPECS[active['type']]['name']}**! Закончите её.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(f"📝 Использование: `/{cmd} [ставка]`\n_Пример: /{cmd} 100_", parse_mode="Markdown")
        return

    try:
        bet = parse_bet(message, parts[1])
    except ValueError as e:
        await message.reply(str(e), parse_mode="Markdown")
        return

    spec = GAME_SPECS[game_type]
    mines = generate_mines(game_type)
    
    db.start_game(message.from_user.id, game_type, bet, mines)
    
    kb = get_game_keyboard(
        current_level=1,
        history={},
        max_levels=spec["levels"],
        width=spec["width"]
    )
    
    await message.reply(
        f"🎮 Игра **{spec['name']}** началась!\n"
        f"💰 Ставка: **{bet:,}** коинов.\n"
        f"📈 Старт: **1.0x**\n\n"
        f"👇 Сделайте выбор на Ряду 1 (самый нижний):",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# === ИГРОВОЙ ИНТЕРФАКТОР (CALLBACKS) ===
@router.callback_query(F.data.startswith("game_action:"))
async def handle_game_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    action = parts[1]

    if action == "locked":
        await callback.answer("🔒 Уровень заблокирован! Сначала пройдите нижний.", show_alert=True)
        return
    if action == "passed":
        await callback.answer("💎 Этот уровень уже успешно пройден!", show_alert=True)
        return
    if action == "ended":
        await callback.answer("🎮 Эта игра уже завершена.", show_alert=True)
        return

    game = db.get_active_game(user_id)
    if not game:
        await callback.answer("❌ Нет активной игры! Начните новую.", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    game_type = game["type"]
    spec = GAME_SPECS[game_type]
    bet = game["bet"]
    current_level = game["current_level"]
    history = game.get("history", {})
    mines = game["mines"]

    if action == "forfeit":
        db.finish_game(user_id, won=False)
        await callback.answer("💸 Вы сдались и потеряли ставку.", show_alert=True)
        
        revealed_kb = get_revealed_keyboard(spec["levels"], spec["width"], mines, history)
        await callback.message.edit_text(
            f"❌ Вы сдались в игре **{spec['name']}**.\n"
            f"💸 Ставка в размере **{bet:,}** коинов сгорела.\n"
            f"💰 Баланс: **{db.get_balance(user_id):,}** коинов.",
            reply_markup=revealed_kb,
            parse_mode="Markdown"
        )
        return

    if action == "cashout":
        multiplier = game["multiplier"]
        payout = db.finish_game(user_id, won=True)
        await callback.answer(f"🎉 Вы успешно вывели {payout:,} коинов!", show_alert=True)
        
        revealed_kb = get_revealed_keyboard(spec["levels"], spec["width"], mines, history)
        await callback.message.edit_text(
            f"🎉 **ПОБЕДА (ВЫВОД)!**\n"
            f"🎮 Игра: **{spec['name']}**\n"
            f"📈 Множитель: **{multiplier}x**\n"
            f"💵 Вы выиграли: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{db.get_balance(user_id):,}** коинов.",
            reply_markup=revealed_kb,
            parse_mode="Markdown"
        )
        return

    if action == "click":
        click_level = int(parts[2])
        click_col = int(parts[3])

        if click_level != current_level:
            await callback.answer("⚠️ Делайте ход на активном ряду!", show_alert=True)
            return

        level_mines = mines[current_level - 1]
        if click_col in level_mines:
            db.finish_game(user_id, won=False)
            await callback.answer("💥 БУМ! Мина!", show_alert=True)
            
            revealed_kb = get_revealed_keyboard(
                spec["levels"], spec["width"], mines, history,
                exploded_lvl=current_level, exploded_col=click_col
            )
            await callback.message.edit_text(
                f"💥 **ВЫ ВЗОРВАЛИСЬ!**\n"
                f"🎮 Игра: **{spec['name']}**\n"
                f"💀 Ошибка на уровне **{current_level}**\n"
                f"💸 Потеряно: **{bet:,}** коинов.\n"
                f"💰 Баланс: **{db.get_balance(user_id):,}** коинов.",
                reply_markup=revealed_kb,
                parse_mode="Markdown"
            )
            return
        else:
            history[str(current_level)] = click_col
            next_level = current_level + 1
            completed_mult = spec["multipliers"][current_level]

            if current_level == spec["levels"]:
                db.update_game_level(user_id, next_level, completed_mult, history)
                payout = db.finish_game(user_id, won=True)
                await callback.answer("🏆 НЕВЕРОЯТНО! ВСЯ СЕТКА ПРОЙДЕНА!", show_alert=True)
                
                revealed_kb = get_revealed_keyboard(spec["levels"], spec["width"], mines, history)
                await callback.message.edit_text(
                    f"🏆 **ГРАНДИОЗНАЯ ПОБЕДА!**\n"
                    f"🎮 Игра: **{spec['name']}**\n"
                    f"📈 Итоговый множитель: **{completed_mult}x**\n"
                    f"💵 Выигрыш: **{payout:,}** коинов!\n"
                    f"💰 Баланс: **{db.get_balance(user_id):,}** коинов.",
                    reply_markup=revealed_kb,
                    parse_mode="Markdown"
                )
            else:
                db.update_game_level(user_id, next_level, completed_mult, history)
                next_mult = spec["multipliers"][next_level]
                
                kb = get_game_keyboard(
                    current_level=next_level,
                    history=history,
                    max_levels=spec["levels"],
                    width=spec["width"]
                )
                
                await callback.message.edit_text(
                    f"🎮 Игра: **{spec['name']}**\n"
                    f"💰 Ставка: **{bet:,}** коинов.\n"
                    f"📈 Фиксированный коэф: **{completed_mult}x** (выигрыш: {int(bet*completed_mult):,})\n"
                    f"🎯 Следующий ряд: **{next_level}** (коэф: **{next_mult}x**)\n\n"
                    f"👇 Выберите ячейку на ряду {next_level}:",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
                await callback.answer("💎 Чисто! Вы поднимаетесь выше.")
