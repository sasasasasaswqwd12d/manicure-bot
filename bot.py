import logging
from telegram import Update, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import database
from keyboards import *
import config
from datetime import datetime
import os
from PIL import Image
import io

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
database.init_db()

# Хранилище временных данных
user_data = {}

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Сохраняем пользователя в БД
    session = database.Session()
    db_user = session.query(database.User).filter_by(user_id=user_id).first()

    if not db_user:
        db_user = database.User(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        session.add(db_user)
        session.commit()

    session.close()

    # Приветственное сообщение
    welcome_text = f"""
    ✨ *Добро пожаловать в Nail Studio!* ✨

    💅 *Я ваш помощник по записи на маникюр и педикюр!*

    🎨 *Что я умею:*
    • Показать услуги и цены
    • Записать вас на удобное время
    • Показать галерею наших работ
    • Связать с администратором
    • Рассказать об акциях

    💖 *Наши преимущества:*
    • Профессиональные мастера
    • Качественные материалы
    • Уютная атмосфера
    • Индивидуальный подход

    Выберите действие в меню ниже 👇
    """

    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "*💅 Наши услуги и цены:*\n\n"

    for service_id, service in config.SERVICES.items():
        text += f"• *{service['name']}* - {service['price']} руб.\n"

    text += "\n👇 Выберите услугу:"

    await update.message.reply_text(
        text,
        reply_markup=services_keyboard(),
        parse_mode='Markdown'
    )

async def gallery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🖼️ *Галерея наших работ*\n\nВыберите категорию:",
        reply_markup=gallery_keyboard(),
        parse_mode='Markdown'
    )

async def contact_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
    📞 *Связь с администраторами*

    💬 *Напишите нам:* @nailstudio_admin
    📱 *Позвоните:* +7 (XXX) XXX-XX-XX
    📍 *Адрес:* г. Москва, ул. Примерная, д. 1

    ⏰ *Часы работы:*
    Пн-Пт: 9:00 - 21:00
    Сб-Вс: 10:00 - 20:00

    💌 *Или оставьте свой вопрос здесь, и мы ответим в течение 15 минут!*
    """

    await update.message.reply_text(
        text,
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

async def about_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
    💖 *О нашем салоне*

    Nail Studio - это место, где рождается красота!

    🌟 *Наша миссия:* делать мир красивее, одну улыбку за раз!

    🎯 *Наши принципы:*
    • Качество выше всего
    • Индивидуальный подход к каждому
    • Постоянное обучение новым техникам
    • Только безопасные материалы

    👩‍🎨 *Наша команда:* 5 профессиональных мастеров
    с опытом работы от 3 лет

    🏆 *Наши достижения:*
    • Лучший nail-салон 2023
    • 1000+ довольных клиентов
    • 98% клиентов возвращаются к нам

    *Ждем вас в нашем уютном салоне!* 💅✨
    """

    await update.message.reply_text(
        text,
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

async def promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
    🎁 *Текущие акции и скидки!*

    🔥 *НОВИЧКАМ:* скидка 20% на первую запись!

    👯 *ПРИВЕДИ ПОДРУГУ:* скидка 15% вам и подруге!

    🎂 *ИМЕНИННИКАМ:* скидка 25% в день рождения!

    ✨ *КОМБО-ПРЕДЛОЖЕНИЕ:*
    Маникюр + Педикюр всего за 2500 руб. (экономия 500 руб.!)

    📅 *УТРЕННИЕ ЧАСЫ:* скидка 10% на запись до 12:00!

    💝 *АКЦИЯ "ВТОРАЯ ПРОЦЕДУРА":*
    При заказе двух процедур - фотосессия в подарок!

    *Спешите записаться! Количество мест ограничено!* 🚀
    """

    await update.message.reply_text(
        text,
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

# ==================== ОБРАБОТКА CALLBACK-ЗАПРОСОВ ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # Сохраняем состояние пользователя
    if user_id not in user_data:
        user_data[user_id] = {}

    # Обработка выбора услуги
    if data.startswith("service_"):
        service_id = data.split("_")[1]
        user_data[user_id]["selected_service"] = service_id

        service = config.SERVICES[service_id]
        await query.edit_message_text(
            f"Вы выбрали: *{service['name']}* - {service['price']} руб.\n\n"
            "📅 Теперь выберите дату:",
            reply_markup=dates_keyboard(),
            parse_mode='Markdown'
        )

    # Выбор даты
    elif data.startswith("date_"):
        selected_date = data.split("_")[1]
        user_data[user_id]["selected_date"] = selected_date

        await query.edit_message_text(
            f"📅 Дата: *{selected_date}*\n\n"
            "⏰ Выберите удобное время:",
            reply_markup=time_keyboard(),
            parse_mode='Markdown'
        )

    # Выбор времени
    elif data.startswith("time_"):
        selected_time = data.split("_")[1]
        user_data[user_id]["selected_time"] = selected_time

        service_id = user_data[user_id].get("selected_service")
        selected_date = user_data[user_id].get("selected_date")

        service = config.SERVICES[service_id]

        text = f"""
📋 *Детали записи:*

💅 *Услуга:* {service['name']}
💰 *Цена:* {service['price']} руб.
📅 *Дата:* {selected_date}
⏰ *Время:* {selected_time}

*Подтверждаете запись?*
        """

        await query.edit_message_text(
            text,
            reply_markup=confirm_keyboard(),
            parse_mode='Markdown'
        )

    # Подтверждение записи
    elif data == "confirm_yes":
        if user_id not in user_data or not all(key in user_data[user_id] for key in ["selected_service", "selected_date", "selected_time"]):
            await query.edit_message_text("❌ Ошибка. Начните запись заново.")
            return

        # Запрашиваем номер телефона
        await query.edit_message_text(
            "📱 *Для завершения записи поделитесь своим контактом:*",
            reply_markup=share_contact(),
            parse_mode='Markdown'
        )

    # Отмена записи
    elif data == "confirm_no":
        await query.edit_message_text(
            "❌ Запись отменена.\n\nВозвращаю в главное меню...",
            reply_markup=main_menu()
        )

    # Назад к услугам
    elif data == "back_to_services":
        await query.edit_message_text(
            "💅 *Наши услуги и цены:*\n\n" +
            "\n".join([f"• *{s['name']}* - {s['price']} руб." for s in config.SERVICES.values()]),
            reply_markup=services_keyboard(),
            parse_mode='Markdown'
        )

    # Назад к главному меню
    elif data == "back_to_main":
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=main_menu()
        )

    # Галерея
    elif data.startswith("gallery_"):
        gallery_type = data.split("_")[1]

        session = database.Session()
        if gallery_type == "all":
            images = session.query(database.ServiceImage).all()
        else:
            images = session.query(database.ServiceImage).filter_by(service_type=gallery_type).all()

        session.close()

        if images:
            for image in images[:3]:  # Показываем максимум 3 фото
                try:
                    with open(image.image_path, 'rb') as f:
                        await context.bot.send_photo(
                            chat_id=query.message.chat_id,
                            photo=InputFile(f),
                            caption=f"💅 Наша работа"
                        )
                except:
                    pass

            if len(images) > 3:
                await query.message.reply_text(
                    f"🖼️ Показано {min(3, len(images))} из {len(images)} работ.\n"
                    "Приходите в салон увидеть больше! 😊",
                    reply_markup=gallery_keyboard()
                )
        else:
            await query.edit_message_text(
                "🖼️ *Галерея пуста.*\n\nАдминистраторы скоро добавят новые работы!",
                reply_markup=gallery_keyboard(),
                parse_mode='Markdown'
            )

# ==================== ОБРАБОТКА КОНТАКТОВ ====================

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if update.message.contact:
        phone = update.message.contact.phone_number

        # Сохраняем телефон в БД
        session = database.Session()
        db_user = session.query(database.User).filter_by(user_id=user_id).first()
        if db_user:
            db_user.phone = phone
            session.commit()

        # Создаем запись в БД
        if user_id in user_data:
            appointment = database.Appointment(
                user_id=user_id,
                service=user_data[user_id].get("selected_service"),
                date=user_data[user_id].get("selected_date"),
                time=user_data[user_id].get("selected_time"),
                status="pending"
            )
            session.add(appointment)
            session.commit()
            appointment_id = appointment.id

            # Получаем данные пользователя
            service_id = user_data[user_id].get("selected_service")
            service = config.SERVICES[service_id]

            # Уведомляем админов
            admin_message = f"""
🚨 *НОВАЯ ЗАПИСЬ!* #{appointment_id}

👤 *Клиент:* {update.message.from_user.full_name}
📱 *Телефон:* {phone}
💅 *Услуга:* {service['name']}
💰 *Цена:* {service['price']} руб.
📅 *Дата:* {user_data[user_id].get('selected_date')}
⏰ *Время:* {user_data[user_id].get('selected_time')}

⚠️ *Требуется подтверждение!*
            """

            for admin_id in config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        reply_markup=admin_decision_keyboard(appointment_id),
                        parse_mode='Markdown'
                    )
                except:
                    pass

        session.close()

        # Подтверждаем пользователю
        await update.message.reply_text(
            "✅ *Запись успешно создана!*\n\n"
            "📞 С вами свяжется администратор для подтверждения записи.\n"
            "⏳ Обычно это занимает не более 30 минут.\n\n"
            "*Спасибо за выбор нашего салона!* 💖",
            reply_markup=main_menu(),
            parse_mode='Markdown'
        )

        # Очищаем временные данные
        if user_id in user_data:
            del user_data[user_id]

# ==================== АДМИН-ПАНЕЛЬ ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in config.ADMIN_IDS:
        await update.message.reply_text(
            "👑 *Панель администратора*",
            reply_markup=admin_menu(),
            parse_mode='Markdown'
        )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id not in config.ADMIN_IDS:
        await query.message.reply_text("⛔ Доступ запрещен!")
        return

    data = query.data

    session = database.Session()

    # Показать заявки на рассмотрении
    if data == "admin_pending":
        appointments = session.query(database.Appointment).filter_by(status="pending").all()

        if appointments:
            text = "📝 *Заявки на рассмотрении:*\n\n"
            for app in appointments:
                user = session.query(database.User).filter_by(user_id=app.user_id).first()
                service = config.SERVICES.get(app.service, {}).get('name', app.service)

                text += f"🔹 *ID {app.id}*\n"
                text += f"👤 {user.first_name if user else 'Неизвестно'}\n"
                text += f"📱 {user.phone if user and user.phone else 'Нет телефона'}\n"
                text += f"💅 {service}\n"
                text += f"📅 {app.date} в {app.time}\n"
                text += "──────────────\n"

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]]),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "✅ Нет заявок на рассмотрении!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]])
            )

    # Одобрить заявку
    elif data.startswith("approve_"):
        appointment_id = int(data.split("_")[1])
        appointment = session.query(database.Appointment).filter_by(id=appointment_id).first()

        if appointment:
            appointment.status = "approved"
            session.commit()

            # Уведомляем клиента
            try:
                user = session.query(database.User).filter_by(user_id=appointment.user_id).first()
                service = config.SERVICES.get(appointment.service, {}).get('name', appointment.service)

                await context.bot.send_message(
                    chat_id=appointment.user_id,
                    text=f"""
🎉 *Ваша запись подтверждена!*

📋 *Детали:*
💅 Услуга: {service}
📅 Дата: {appointment.date}
⏰ Время: {appointment.time}

📍 *Адрес:* г. Москва, ул. Примерная, д. 1
📱 *Телефон салона:* +7 (XXX) XXX-XX-XX

⚠️ *Пожалуйста, приходите за 5-10 минут до записи!*

*Ждем вас!* 💖
                    """,
                    parse_mode='Markdown'
                )
            except:
                pass

            await query.edit_message_text(
                f"✅ Запись #{appointment_id} одобрена!\nКлиент уведомлен.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_pending")]])
            )

    # Отклонить заявку
    elif data.startswith("reject_"):
        appointment_id = int(data.split("_")[1])
        appointment = session.query(database.Appointment).filter_by(id=appointment_id).first()

        if appointment:
            appointment.status = "rejected"
            session.commit()

            # Уведомляем клиента
            try:
                await context.bot.send_message(
                    chat_id=appointment.user_id,
                    text="😔 *К сожалению, администратор отклонил вашу запись.*\n\n"
                         "Пожалуйста, выберите другое время или свяжитесь с нами для уточнения деталей.",
                    parse_mode='Markdown'
                )
            except:
                pass

            await query.edit_message_text(
                f"❌ Запись #{appointment_id} отклонена!\nКлиент уведомлен.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_pending")]])
            )

    # Добавить фото
    elif data == "admin_add_photo":
        await query.edit_message_text(
            "🖼️ *Добавление фото в галерею*\n\n"
            "Пришлите фото и укажите тип через пробел:\n"
            "• manicure - для маникюра\n"
            "• pedicure - для педикюра\n"
            "• combo - для комбо\n\n"
            "*Пример:* manicure",
            parse_mode='Markdown'
        )
        context.user_data["awaiting_photo"] = True

    # Статистика
    elif data == "admin_stats":
        total_users = session.query(database.User).count()
        total_appointments = session.query(database.Appointment).count()
        pending_appointments = session.query(database.Appointment).filter_by(status="pending").count()
        approved_appointments = session.query(database.Appointment).filter_by(status="approved").count()

        text = f"""
📊 *Статистика салона:*

👥 Всего клиентов: *{total_users}*
📅 Всего записей: *{total_appointments}*
⏳ Ожидают подтверждения: *{pending_appointments}*
✅ Подтверждено: *{approved_appointments}*

💸 *Доход (подтвержденные):*
"""

        # Расчет дохода
        appointments = session.query(database.Appointment).filter_by(status="approved").all()
        total_income = 0
        for app in appointments:
            service = config.SERVICES.get(app.service, {})
            total_income += service.get('price', 0)

        text += f"💰 Общий доход: *{total_income}* руб.\n"
        text += f"📈 Средний чек: *{total_income // approved_appointments if approved_appointments > 0 else 0}* руб."

        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]])
        )

    # Назад в админ-меню
    elif data == "back_to_admin":
        await query.edit_message_text(
            "👑 *Панель администратора*",
            reply_markup=admin_menu(),
            parse_mode='Markdown'
        )

    session.close()

# ==================== ОБРАБОТКА ФОТО ДЛЯ АДМИНА ====================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in config.ADMIN_IDS and context.user_data.get("awaiting_photo"):
        photo = update.message.photo[-1]
        caption = update.message.caption

        if not caption:
            await update.message.reply_text("❌ Укажите тип фото (manicure/pedicure/combo)")
            return

        service_type = caption.strip().lower()

        if service_type not in ['manicure', 'pedicure', 'combo']:
            await update.message.reply_text("❌ Неверный тип. Используйте: manicure, pedicure или combo")
            return

        # Скачиваем фото
        photo_file = await context.bot.get_file(photo.file_id)

        # Создаем директорию для фото, если её нет
        os.makedirs("images", exist_ok=True)

        # Сохраняем фото
        filename = f"images/{service_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        await photo_file.download_to_drive(filename)

        # Сохраняем в БД
        session = database.Session()
        service_image = database.ServiceImage(
            service_type=service_type,
            image_path=filename
        )
        session.add(service_image)
        session.commit()
        session.close()

        await update.message.reply_text(
            f"✅ Фото добавлено в галерею ({service_type})!",
            reply_markup=admin_menu()
        )

        context.user_data["awaiting_photo"] = False

# ==================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ====================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📋 Услуги и цены":
        await services(update, context)

    elif text == "🖼️ Галерея работ":
        await gallery(update, context)

    elif text == "📅 Записаться":
        await services(update, context)

    elif text == "📞 Связаться с админами":
        await contact_admins(update, context)

    elif text == "⭐ Отзывы":
        await update.message.reply_text(
            "⭐ *Отзывы наших клиентов:*\n\n"
            "💖 *Анна:* 'Лучший маникюр в моей жизни! Мастера - волшебницы!'\n"
            "✨ *Мария:* 'Хожу уже год, всегда идеально. Спасибо!'\n"
            "🌟 *Елена:* 'Чисто, красиво, профессионально. Рекомендую!'\n"
            "🎀 *Ольга:* 'Атмосфера просто космос! Вернусь еще не раз!'\n\n"
            "*Нам очень приятно! Спасибо за ваши отзывы!* 😊",
            parse_mode='Markdown'
        )

    elif text == "ℹ️ О нас":
        await about_us(update, context)

    elif text == "🎁 Акции":
        await promotions(update, context)

    elif text == "/admin" or text == "👑 Админка":
        await admin_panel(update, context)

    else:
        # Если это просто текст (возможно, вопрос)
        if len(text) > 10:  # Если сообщение достаточно длинное
            # Пересылаем админам
            for admin_id in config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"💬 *Вопрос от клиента:*\n\n{text}\n\n👤 *От:* {update.message.from_user.full_name}",
                        parse_mode='Markdown'
                    )
                except:
                    pass

            await update.message.reply_text(
                "💌 *Ваше сообщение отправлено администраторам!*\n\n"
                "Они ответят вам в ближайшее время. Обычно это занимает не более 15 минут! ⏳",
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))

    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_|^approve_|^reject_|^back_to_admin"))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Запускаем бота
    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки.")
    application.run_polling(allowed_updates=Update.ALL_UPDATES)

if __name__ == '__main__':
    main()
