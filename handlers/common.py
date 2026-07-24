from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from database import db

router = Router()

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
        f"• `/pyramid [ставка]` — Пирамида (4 ячейки в ширину, 12 в высоту)\n\n"
        f"🎁 **Ежечасный бонус:**\n"
        f"• `/bonus` — Получить случайный бонус от 1 до 10 000 коинов!\n\n"
        f"📊 **Баланс:**\n"
        f"• `/balance` — Проверить счет"
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
