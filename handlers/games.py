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
        if chosen_multiplier <= 1.0: raise ValueError()
    except ValueError as e:
        msg = str(e) if "❌" in str(e) else "❌ Ошибка в ставке или коэффициенте."
        await message.reply(msg, parse_mode="Markdown")
        return

    crash_point = generate_crash_multiplier()
    db.update_balance(message.from_user.id, -bet)

    if crash_point >= chosen_multiplier:
        payout = int(bet * chosen_multiplier)
        new_bal = db.update_balance(message.from_user.id, payout)
        await message.reply(
            f"📈 **КРАШ**\n🚀 Ракета долетела до: **{crash_point:.2f}x**\n"
            f"🎉 Победитель: {message.from_user.mention_markdown()}\n"
            f"🎯 Коэффициент: **{chosen_multiplier:.2f}x**\n"
            f"💵 Выигрыш: **{payout:,}** коинов\n"
            f"💰 Ваш баланс: **{new_bal:,}**", 
            parse_mode="Markdown"
        )
    else:
        await message.reply(
            f"📈 **КРАШ**\n💥 Ракету разорвало на: **{crash_point:.2f}x**\n"
            f"❌ Проигравший: {message.from_user.mention_markdown()}\n"
            f"💸 Потеряно: **{bet:,}** коинов\n"
            f"💰 Ваш баланс: **{db.get_balance(message.from_user.id):,}**", 
            parse_mode="Markdown"
        )

# === ИГРЫ НА ПОЛЕ ===
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
        return

    spec = GAME_SPECS[game["type"]]

    if action == "cashout":
        payout = db.finish_game(user_id, won=True)
        await callback.message.edit_text(
            f"🎉 **ВЫИГРЫШ ЗАБРАН!**\n👤 {callback.from_user.mention_markdown()}\n"
            f"📈 Итоговый коэф: **{game['multiplier']}x**\n"
            f"💵 Сумма: **{payout:,}** коинов\n💰 Баланс: **{db.get_balance(user_id):,}**",
            reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"]),
            parse_mode="Markdown"
        )
        return

    if action == "forfeit":
        db.finish_game(user_id, won=False)
        await callback.message.edit_text(
            f"❌ **ИГРА ОКОНЧЕНА (СДАЧА)**\n👤 {callback.from_user.mention_markdown()}\n"
            f"💸 Потеряно: **{game['bet']:,}** коинов.",
            reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"]),
            parse_mode="Markdown"
        )
        return

    if action == "click":
        lvl, col = int(parts[2]), int(parts[3])
        if lvl != game["current_level"]: return

        if col in game["mines"][lvl-1]:
            db.finish_game(user_id, won=False)
            await callback.message.edit_text(
                f"💥 **БУМ! МИНА!**\n👤 {callback.from_user.mention_markdown()}\n"
                f"💀 Вы взорвались на {lvl} ряду.\n💸 Потеряно: **{game['bet']:,}** коинов.",
                reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], game["history"], lvl, col),
                parse_mode="Markdown"
            )
        else:
            history = game["history"]
            history[str(lvl)] = col
            new_mult = spec["multipliers"][lvl]
            if lvl == spec["levels"]:
                db.update_game_level(user_id, lvl+1, new_mult, history)
                payout = db.finish_game(user_id, won=True)
                await callback.message.edit_text(
                    f"🏆 **ПОЛНАЯ ПОБЕДА!**\n👤 {callback.from_user.mention_markdown()}\n"
                    f"📈 Множитель: **{new_mult}x**\n"
                    f"💵 Выигрыш: **{payout:,}** коинов!",
                    reply_markup=get_revealed_keyboard(spec["levels"], spec["width"], game["mines"], history),
                    parse_mode="Markdown"
                )
            else:
                db.update_game_level(user_id, lvl+1, new_mult, history)
                await callback.message.edit_reply_markup(
                    reply_markup=get_game_keyboard(lvl+1, history, spec["levels"], spec["width"], user_id)
                )
        await callback.answer()
