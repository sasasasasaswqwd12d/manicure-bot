from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///manicure.db")

# Услуги и цены
SERVICES = {
    "manicure": {"name": "Маникюр", "price": 1500},
    "pedicure": {"name": "Педикюр", "price": 1500},
    "combo": {"name": "Комбо (маникюр + педикюр)", "price": 2500}
}

# Временные слоты
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00", "14:00",
    "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"
]
