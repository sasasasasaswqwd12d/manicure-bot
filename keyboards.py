from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import config

# Главное меню
def main_menu():
    keyboard = [
        [KeyboardButton("📋 Услуги и цены")],
        [KeyboardButton("🖼️ Галерея работ")],
        [KeyboardButton("📅 Записаться")],
        [KeyboardButton("📞 Связаться с админами"), KeyboardButton("⭐ Отзывы")],
        [KeyboardButton("ℹ️ О нас"), KeyboardButton("🎁 Акции")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Услуги
def services_keyboard():
    keyboard = []
    for service_id, service in config.SERVICES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{service['name']} - {service['price']} руб.",
                callback_data=f"service_{service_id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

# Выбор даты (упрощенно - следующие 7 дней)
def dates_keyboard():
    import datetime
    keyboard = []
    today = datetime.date.today()

    for i in range(1, 8):
        date = today + datetime.timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date.weekday()]
        keyboard.append([
            InlineKeyboardButton(
                f"{date_str} ({weekday})",
                callback_data=f"date_{date_str}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_services")])
    return InlineKeyboardMarkup(keyboard)

# Выбор времени
def time_keyboard():
    keyboard = []
    row = []

    for i, time_slot in enumerate(config.TIME_SLOTS):
        row.append(InlineKeyboardButton(time_slot, callback_data=f"time_{time_slot}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_dates")])
    return InlineKeyboardMarkup(keyboard)

# Подтверждение записи
def confirm_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Админ меню
def admin_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Заявки на рассмотрении", callback_data="admin_pending")],
        [InlineKeyboardButton("📅 Все записи", callback_data="admin_all_appointments")],
        [InlineKeyboardButton("🖼️ Добавить фото", callback_data="admin_add_photo")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Кнопки для админа (одобрить/отклонить)
def admin_decision_keyboard(appointment_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{appointment_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{appointment_id}")
        ],
        [
            InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{appointment_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Галерея
def gallery_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💅 Маникюр", callback_data="gallery_manicure"),
            InlineKeyboardButton("👣 Педикюр", callback_data="gallery_pedicure")
        ],
        [
            InlineKeyboardButton("🌟 Комбо", callback_data="gallery_combo"),
            InlineKeyboardButton("🎨 Все работы", callback_data="gallery_all")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Кнопка "Поделиться контактом"
def share_contact():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
