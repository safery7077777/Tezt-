import math
from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from database import db
from config import ADMIN_ID_LIST # Для профиля

router = Router()

def format_balance(amount: int) -> str:
    """Форматирует число в 'k', 'kk', 'm' или 'kkk' формат для больших чисел."""
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.2f}kkk"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}kk"
    if amount >= 1_000:
        return f"{amount / 1_000:.2f}k"
    return f"{amount:,}" # Обычное форматирование для меньших чисел


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    user = db.get_user(user_id, username)
    
    welcome = (
        f"👋 Привет, **{message.from_user.full_name}**!\n"
        f"Добро пожаловать в игровой бот **Kratz | mines**! 🎰\n\n"
        f"💰 Твой стартовый баланс: **{user['balance']:,}** коинов.\n\n"
        f"🎮 **Наши игры:**\n"
        f"• `/crash [ставка] [коэф]` — Краш игра\n"
        f"• `/tower [ставка]` — Башня (5 ячеек в ширину, 9 в высоту)\n"
        f"• `/diamonds [ставка]` — Алмазы (3 ячейки в ширину, 16 в высоту)\n"
        f"• `/pyramid [ставка]` — Пирамида (4 ячейки в ширину, 12 в высоту)\n"
        f"• `/рулетка [ставка] [число/цвет/чет]` — Рулетка\n"
        f"• `/guess [ставка] [число] [макс_диапазон]` — Угадай число\n"
        f"• `/кубик [кол-во кубов] [меньше/больше/число] [ставка]` — Кубики\n\n"
        f"🎁 **Ежечасный бонус:**\n"
        f"• `/bonus` — Получить случайный бонус от 1 до 10 000 коинов!\n\n"
        f"📊 **Информация:**\n"
        f"• `/balance` — Проверить счет\n"
        f"• `/профиль` — Посмотреть свой профиль\n"
        f"• `/дать [юзернейм/ID] [сумма]` — Передача коинов другому игроку"
    )
    await message.reply(welcome, parse_mode="Markdown")

@router.message(Command("balance", "баланс"))
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    balance = db.get_balance(user_id)
    await message.reply(f"💰 Ваш текущий баланс: **{balance:,}** коинов.", parse_mode="Markdown")

@router.message(Command("bonus", "бонус"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    success, result = db.claim_bonus(user_id)
    if success:
        await message.reply(f"🎁 Вы забрали ежечасный бонус: **+{result:,}** коинов!", parse_mode="Markdown")
    else:
        await message.reply(f"⏳ Бонус уже получен! Следующая попытка через: **{result}**.", parse_mode="Markdown")

@router.message(Command("профиль", "profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id) # Гарантируем, что пользователь есть в БД
    
    # Расчет оборота и проигранных
    total_won = user_data.get('won', 0)
    total_lost = user_data.get('lost', 0)
    total_turnover = total_won + total_lost
    
    # Форматирование даты регистрации
    reg_date_utc = datetime.fromisoformat(user_data["registration_date"])
    reg_date_local = reg_date_utc.strftime("%d-%m-%Y %H:%M") # Можно указать нужный часовой пояс, по умолчанию UTC

    status = "Админ" if user_id in ADMIN_ID_LIST else "Игрок"

    profile_text = (
        f"🆔 Профиль: `{user_id}`\n"
        f"·····················\n"
        f"├ 👤 **{message.from_user.full_name}**\n"
        f"├ ⚡️ Статус: **{status}**\n"
        f"├ 🎮 Сыграно игр: **{user_data.get('games', 0):,}**\n"
        f"├ 🔄 Оборот: **{format_balance(total_turnover)}** m¢\n"
        f"├ 📉 Проиграно: **{format_balance(total_lost)}** m¢\n"
        f"📅 Дата регистрации: **{reg_date_local}**\n"
        f"·····················\n"
        f"💰 Баланс: **{user_data['balance']:,}** mCoin"
    )
    await message.reply(profile_text, parse_mode="Markdown")

@router.message(Command("дать", "transfer"))
async def cmd_transfer_coins(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Использование: `/дать [юзернейм_или_ID] [количество]`", parse_mode="Markdown")
        return

    target_input = parts[1].strip()
    amount_str = parts[2].strip()

    try:
        amount = int(amount_str)
        if amount <= 0:
            raise ValueError("❌ Количество коинов должно быть больше нуля.")
    except ValueError:
        await message.reply("❌ Количество коинов должно быть целым положительным числом.")
        return

    sender_id = message.from_user.id
    sender_balance = db.get_balance(sender_id)

    if sender_balance < amount:
        await message.reply(f"❌ Недостаточно средств! Ваш баланс: **{sender_balance:,}** коинов.", parse_mode="Markdown")
        return

    target_uid, target_user_data = db.get_user_by_username(target_input)
    if not target_uid:
        await message.reply(
            f"❌ Пользователь `{target_input}` не найден.\nОн должен написать боту хотя бы один раз.",
            parse_mode="Markdown"
        )
        return
    
    if int(target_uid) == sender_id:
        await message.reply("❌ Вы не можете передать коины самому себе.", parse_mode="Markdown")
        return

    # Списание с отправителя
    db.update_balance(sender_id, -amount)
    # Начисление получателю
    db.update_balance(int(target_uid), amount)

    sender_new_balance = db.get_balance(sender_id)
    target_new_balance = db.get_balance(int(target_uid))

    await message.reply(
        f"✅ Вы успешно передали **{amount:,}** коинов пользователю `{target_input}`.\n"
        f"💰 Ваш новый баланс: **{sender_new_balance:,}** коинов.",
        parse_mode="Markdown"
    )
    # Оповещаем получателя, если это возможно (бот должен быть в личке или общей группе)
    try:
        await message.bot.send_message(
            chat_id=int(target_uid),
            text=f"🎁 Вам передали **{amount:,}** коинов!\n"
                 f"От пользователя: {message.from_user.mention_markdown()}\n"
                 f"💰 Ваш текущий баланс: **{target_new_balance:,}** коинов.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о передаче коинов пользователю {target_uid}: {e}")
