import json
import os
import logging
from datetime import datetime, timedelta
from threading import Lock
from config import settings

logger = logging.getLogger(__name__)
DB_FILE = "database.json"

class Database:
    def __init__(self, filename=DB_FILE):
        self.filename = filename
        self.lock = Lock()
        self.data = {"users": {}, "active_games": {}}
        self.load()

    def load(self):
        with self.lock:
            if os.path.exists(self.filename):
                try:
                    with open(self.filename, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
                        if "users" not in self.data:
                            self.data["users"] = {}
                        if "active_games" not in self.data:
                            self.data["active_games"] = {}
                except Exception as e:
                    logger.error(f"Ошибка чтения БД: {e}. Создаем пустую.")
                    self.data = {"users": {}, "active_games": {}}
            else:
                self.save_unlocked()

    def save(self):
        with self.lock:
            self.save_unlocked()

    def save_unlocked(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения БД: {e}")

    def get_user(self, user_id: int, username: str = None) -> dict:
        uid = str(user_id)
        with self.lock:
            if uid not in self.data["users"]:
                self.data["users"][uid] = {
                    "balance": settings.START_BALANCE,
                    "last_bonus": None,
                    "username": username.lower() if username else None
                }
                self.save_unlocked()
            else:
                if username and self.data["users"][uid].get("username") != username.lower():
                    self.data["users"][uid]["username"] = username.lower()
                    self.save_unlocked()
            return self.data["users"][uid]

    def get_user_by_username(self, username: str) -> tuple:
        username_lower = username.lower().replace("@", "")
        with self.lock:
            for uid, user in self.data["users"].items():
                if user.get("username") == username_lower:
                    return uid, user
            if username_lower.isdigit():
                uid = username_lower
                if uid in self.data["users"]:
                    return uid, self.data["users"][uid]
        return None, None

    def update_balance(self, user_id: int, amount: int) -> int:
        uid = str(user_id)
        self.get_user(user_id)
        with self.lock:
            current_bal = self.data["users"][uid]["balance"]
            new_bal = current_bal + amount
            if new_bal < 0:
                new_bal = 0
            if new_bal > settings.MAX_BALANCE:
                new_bal = settings.MAX_BALANCE
            self.data["users"][uid]["balance"] = int(new_bal)
            self.save_unlocked()
            return int(new_bal)

    def get_balance(self, user_id: int) -> int:
        return self.get_user(user_id).get("balance", 0)

    def claim_bonus(self, user_id: int) -> tuple:
        uid = str(user_id)
        self.get_user(user_id)
        import random
        with self.lock:
            user = self.data["users"][uid]
            last_bonus_str = user.get("last_bonus")
            now = datetime.utcnow()
            
            if last_bonus_str:
                last_bonus = datetime.fromisoformat(last_bonus_str)
                cooldown = timedelta(hours=1)
                if now - last_bonus < cooldown:
                    remaining = cooldown - (now - last_bonus)
                    mins, secs = divmod(remaining.seconds, 60)
                    return False, f"{mins}м {secs}с"
            
            bonus_amount = random.randint(1, 10000)
            current_bal = user["balance"]
            new_bal = min(current_bal + bonus_amount, settings.MAX_BALANCE)
            actual_added = new_bal - current_bal
            
            user["balance"] = new_bal
            user["last_bonus"] = now.isoformat()
            self.save_unlocked()
            return True, actual_added

    def get_active_game(self, user_id: int) -> dict:
        uid = str(user_id)
        with self.lock:
            return self.data["active_games"].get(uid)

    def start_game(self, user_id: int, game_type: str, bet: int, mines: list):
        uid = str(user_id)
        with self.lock:
            self.data["active_games"][uid] = {
                "type": game_type,
                "bet": bet,
                "current_level": 1,
                "multiplier": 1.0,
                "mines": mines,
                "history": {}
            }
            self.data["users"][uid]["balance"] -= bet
            self.save_unlocked()

    def update_game_level(self, user_id: int, level: int, multiplier: float, history: dict):
        uid = str(user_id)
        with self.lock:
            if uid in self.data["active_games"]:
                self.data["active_games"][uid]["current_level"] = level
                self.data["active_games"][uid]["multiplier"] = multiplier
                self.data["active_games"][uid]["history"] = history
                self.save_unlocked()

    def finish_game(self, user_id: int, won: bool) -> int:
        uid = str(user_id)
        payout = 0
        with self.lock:
            game = self.data["active_games"].get(uid)
            if game:
                if won:
                    payout = int(game["bet"] * game["multiplier"])
                    current_bal = self.data["users"][uid]["balance"]
                    new_bal = min(current_bal + payout, settings.MAX_BALANCE)
                    self.data["users"][uid]["balance"] = new_bal
                del self.data["active_games"][uid]
                self.save_unlocked()
        return payout

db = Database()
