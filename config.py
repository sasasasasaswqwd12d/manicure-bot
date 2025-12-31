from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///manicure.db")

# Услуги и цены
SERVICES = {
    "manicure": {"name": "Маникюр", "price": 1500, "emoji": "💅", "duration": 90},
    "pedicure": {"name": "Педикюр", "price": 1500, "emoji": "👣", "duration": 90},
    "combo": {"name": "Комбо", "price": 2500, "emoji": "🌟", "duration": 150, "description": "Маникюр + Педикюр"}
}

# Временные слоты
TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00", "15:00",
    "16:00", "17:00", "18:00", "19:00", "20:00"
]

# Контакты салона
SALON_INFO = {
    "address": "г. Мытищи, ул. Силикатная, 49 к3",
    "phone": "+7 (926) 373-90-44",
    "phone_formatted": "89263739044",
    "working_hours": "Ежедневно с 10:00 до 21:00",
    "metro": "Ближайшее метро: Медведково"
}

# Система скидок и лояльности
LOYALTY_SYSTEM = {
    "first_visit_discount": 20,  # 20% скидка на первую запись
    "referral_bonus": 15,        # 15% скидка за приведенного друга
    "birthday_discount": 25,     # 25% скидка в день рождения
    "visit_milestones": {
        5: 10,   # 10% скидка после 5 визитов
        10: 15,  # 15% скидка после 10 визитов
        20: 20,  # 20% скидка после 20 визитов
    }
}

# Напоминания
REMINDERS = {
    "24_hours": True,
    "3_hours": True,
    "after_visit": True,
}
