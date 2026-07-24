from aiogram import Router, types
from aiogram.filters import Command
from config import ADMIN_ID_LIST, ADMIN_USERNAME_LIST
from database import db

router = Router()

def is_admin(user: types.User) -> bool:
    if user.id in ADMIN_ID_LIST:
        return True
    if user.username and user.username.lower() in ADMIN_USERNAME_LIST:
        return True
    return False

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
