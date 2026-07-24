import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: str = "8498065644,7727345054"          # Telegram ID админов через запятую
    ADMIN_USERNAMES: str = "Kratz_future, nmproda"    # Юзернеймы админов через запятую (без @)
    START_BALANCE: int = 5000    # Начальный баланс новых игроков
    MAX_BALANCE: int = 999999999999999  # Лимит убран (999 триллионов)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Предварительный парсинг списков администраторов
ADMIN_ID_LIST = [int(x.strip()) for x in settings.ADMIN_IDS.split(",") if x.strip().isdigit()]
ADMIN_USERNAME_LIST = [x.strip().lower() for x in settings.ADMIN_USERNAMES.split(",") if x.strip()]
