import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove,
    FSInputFile, Contact
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import database
import config
from database import Session, User, Appointment, ServiceImage
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Состояния для FSM
class AppointmentStates(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()
    waiting_for_contact = State()
    waiting_for_question = State()

class AdminStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_photo_type = State()
    waiting_for_broadcast = State()

# ==================== КЛАВИАТУРЫ ====================

def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Услуги и цены")
    builder.button(text="🖼️ Галерея работ")
    builder.button(text="📅 Записаться")
    builder.button(text="📞 Связаться с админами")
    builder.button(text="⭐ Отзывы")
    builder.button(text="ℹ️ О нас")
    builder.button(text="🎁 Акции")
    builder.adjust(2, 2, 1, 2)
    return builder.as_markup(resize_keyboard=True)

def services_keyboard():
    builder = InlineKeyboardBuilder()
    for service_id, service in config.SERVICES.items():
        builder.button(
            text=f"{service['name']} - {service['price']} руб.",
            callback_data=f"service_{service_id}"
        )
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def dates_keyboard():
    builder = InlineKeyboardBuilder()
    today = datetime.now().date()

    for i in range(1, 8):
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date.weekday()]
        builder.button(
            text=f"{date_str} ({weekday})",
            callback_data=f"date_{date_str}"
        )

    builder.button(text="🔙 Назад", callback_data="back_to_services")
    builder.adjust(2)
    return builder.as_markup()

def time_keyboard():
    builder = InlineKeyboardBuilder()

    for time_slot in config.TIME_SLOTS:
        builder.button(text=time_slot, callback_data=f"time_{time_slot}")

    builder.button(text="🔙 Назад", callback_data="back_to_dates")
    builder.adjust(3)
    return builder.as_markup()

def confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_yes")
    builder.button(text="❌ Отменить", callback_data="confirm_no")
    return builder.as_markup()

def gallery_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💅 Маникюр", callback_data="gallery_manicure")
    builder.button(text="👣 Педикюр", callback_data="gallery_pedicure")
    builder.button(text="🌟 Комбо", callback_data="gallery_combo")
    builder.button(text="🎨 Все работы", callback_data="gallery_all")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def admin_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📝 Заявки на рассмотрении", callback_data="admin_pending")
    builder.button(text="📅 Все записи", callback_data="admin_all_appointments")
    builder.button(text="🖼️ Добавить фото", callback_data="admin_add_photo")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.adjust(2)
    return builder.as_markup()

def admin_decision_keyboard(appointment_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"approve_{appointment_id}")
    builder.button(text="❌ Отклонить", callback_data=f"reject_{appointment_id}")
    builder.button(text="💬 Комментарий", callback_data=f"comment_{appointment_id}")
    builder.adjust(2, 1)
    return builder.as_markup()

def share_contact():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Поделиться контактом", request_contact=True)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user

    # Сохраняем пользователя в БД
    session = Session()
    db_user = session.query(User).filter_by(user_id=user.id).first()

    if not db_user:
        db_user = User(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        session.add(db_user)
        session.commit()

    session.close()

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

    await message.answer(welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id in config.ADMIN_IDS:
        await message.answer("👑 *Панель администратора*", reply_markup=admin_menu(), parse_mode='Markdown')
    else:
        await message.answer("⛔ Доступ запрещен!")

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================

@dp.message(F.text == "📋 Услуги и цены")
async def show_services(message: Message):
    text = "*💅 Наши услуги и цены:*\n\n"

    for service_id, service in config.SERVICES.items():
        text += f"• *{service['name']}* - {service['price']} руб.\n"

    text += "\n👇 Выберите услугу:"

    await message.answer(text, reply_markup=services_keyboard(), parse_mode='Markdown')

@dp.message(F.text == "🖼️ Галерея работ")
async def show_gallery(message: Message):
    await message.answer("🖼️ *Галерея наших работ*\n\nВыберите категорию:",
                        reply_markup=gallery_keyboard(), parse_mode='Markdown')

@dp.message(F.text == "📅 Записаться")
async def start_appointment(message: Message, state: FSMContext):
    await show_services(message)
    await state.set_state(AppointmentStates.choosing_service)

@dp.message(F.text == "📞 Связаться с админами")
async def contact_admins(message: Message):
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
    await message.answer(text, reply_markup=main_menu(), parse_mode='Markdown')

@dp.message(F.text == "⭐ Отзывы")
async def show_reviews(message: Message):
    text = """
⭐ *Отзывы наших клиентов:*

💖 *Анна:* 'Лучший маникюр в моей жизни! Мастера - волшебницы!'
✨ *Мария:* 'Хожу уже год, всегда идеально. Спасибо!'
🌟 *Елена:* 'Чисто, красиво, профессионально. Рекомендую!'
🎀 *Ольга:* 'Атмосфера просто космос! Вернусь еще не раз!'

*Нам очень приятно! Спасибо за ваши отзывы!* 😊
    """
    await message.answer(text, parse_mode='Markdown')

@dp.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
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
    await message.answer(text, reply_markup=main_menu(), parse_mode='Markdown')

@dp.message(F.text == "🎁 Акции")
async def show_promotions(message: Message):
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
    await message.answer(text, reply_markup=main_menu(), parse_mode='Markdown')

# ==================== ОБРАБОТКА CALLBACK ЗАПРОСОВ ====================

@dp.callback_query(F.data.startswith("service_"))
async def process_service(callback: CallbackQuery, state: FSMContext):
    service_id = callback.data.split("_")[1]
    service = config.SERVICES[service_id]

    await state.update_data(selected_service=service_id)
    await state.set_state(AppointmentStates.choosing_date)

    await callback.message.edit_text(
        f"Вы выбрали: *{service['name']}* - {service['price']} руб.\n\n"
        "📅 Теперь выберите дату:",
        reply_markup=dates_keyboard(),
        parse_mode='Markdown'
    )

@dp.callback_query(F.data.startswith("date_"))
async def process_date(callback: CallbackQuery, state: FSMContext):
    selected_date = callback.data.split("_")[1]

    await state.update_data(selected_date=selected_date)
    await state.set_state(AppointmentStates.choosing_time)

    await callback.message.edit_text(
        f"📅 Дата: *{selected_date}*\n\n"
        "⏰ Выберите удобное время:",
        reply_markup=time_keyboard(),
        parse_mode='Markdown'
    )

@dp.callback_query(F.data.startswith("time_"))
async def process_time(callback: CallbackQuery, state: FSMContext):
    selected_time = callback.data.split("_")[1]
    await state.update_data(selected_time=selected_time)

    data = await state.get_data()
    service = config.SERVICES[data['selected_service']]

    text = f"""
📋 *Детали записи:*

💅 *Услуга:* {service['name']}
💰 *Цена:* {service['price']} руб.
📅 *Дата:* {data['selected_date']}
⏰ *Время:* {selected_time}

*Подтверждаете запись?*
    """

    await callback.message.edit_text(
        text,
        reply_markup=confirm_keyboard(),
        parse_mode='Markdown'
    )
    await state.set_state(AppointmentStates.confirming)

@dp.callback_query(F.data == "confirm_yes")
async def confirm_appointment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📱 *Для завершения записи поделитесь своим контактом:*",
        reply_markup=share_contact(),
        parse_mode='Markdown'
    )
    await state.set_state(AppointmentStates.waiting_for_contact)

@dp.callback_query(F.data == "confirm_no")
async def cancel_appointment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Запись отменена.")
    await callback.message.answer("Возвращаю в главное меню...", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:")
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery):
    text = "*💅 Наши услуги и цены:*\n\n"
    for service_id, service in config.SERVICES.items():
        text += f"• *{service['name']}* - {service['price']} руб.\n"
    text += "\n👇 Выберите услугу:"

    await callback.message.edit_text(text, reply_markup=services_keyboard(), parse_mode='Markdown')

@dp.callback_query(F.data == "back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = config.SERVICES[data.get('selected_service', 'manicure')]

    await callback.message.edit_text(
        f"Вы выбрали: *{service['name']}* - {service['price']} руб.\n\n"
        "📅 Теперь выберите дату:",
        reply_markup=dates_keyboard(),
        parse_mode='Markdown'
    )
    await state.set_state(AppointmentStates.choosing_date)

@dp.callback_query(F.data.startswith("gallery_"))
async def show_gallery_images(callback: CallbackQuery):
    gallery_type = callback.data.split("_")[1]

    session = Session()
    if gallery_type == "all":
        images = session.query(ServiceImage).all()
    else:
        images = session.query(ServiceImage).filter_by(service_type=gallery_type).all()

    if not images:
        await callback.message.edit_text(
            "🖼️ *Галерея пуста.*\n\nАдминистраторы скоро добавят новые работы!",
            reply_markup=gallery_keyboard(),
            parse_mode='Markdown'
        )
        session.close()
        return

    sent_count = 0
    for image in images[:3]:
        try:
            if os.path.exists(image.image_path):
                await callback.message.answer_photo(
                    FSInputFile(image.image_path),
                    caption=f"💅 Наша работа"
                )
                sent_count += 1
            else:
                logger.warning(f"Файл не найден: {image.image_path}")
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")

    session.close()

    if sent_count == 0:
        await callback.message.edit_text(
            "🖼️ *Фотографии временно недоступны*\n\nПриходите в салон увидеть наши работы! 😊",
            reply_markup=gallery_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await callback.message.answer(
            f"🖼️ Показано {sent_count} работ.\nПриходите в салон увидеть больше! 😊",
            reply_markup=gallery_keyboard()
        )

# ==================== ОБРАБОТКА КОНТАКТОВ ====================

@dp.message(F.contact)
async def process_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    user_id = message.from_user.id

    session = Session()

    # Сохраняем телефон в БД
    db_user = session.query(User).filter_by(user_id=user_id).first()
    if db_user:
        db_user.phone = phone
        session.commit()

    # Получаем данные из состояния
    data = await state.get_data()

    if all(key in data for key in ['selected_service', 'selected_date', 'selected_time']):
        # Создаем запись в БД
        appointment = Appointment(
            user_id=user_id,
            service=data['selected_service'],
            date=data['selected_date'],
            time=data['selected_time'],
            status="pending"
        )
        session.add(appointment)
        session.commit()
        appointment_id = appointment.id

        # Получаем данные услуги
        service = config.SERVICES[data['selected_service']]

        # Уведомляем админов
        admin_message = f"""
🚨 *НОВАЯ ЗАПИСЬ!* #{appointment_id}

👤 *Клиент:* {message.from_user.full_name}
📱 *Телефон:* {phone}
💅 *Услуга:* {service['name']}
💰 *Цена:* {service['price']} руб.
📅 *Дата:* {data['selected_date']}
⏰ *Время:* {data['selected_time']}

⚠️ *Требуется подтверждение!*
        """

        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    reply_markup=admin_decision_keyboard(appointment_id),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")

        # Подтверждаем пользователю
        await message.answer(
            "✅ *Запись успешно создана!*\n\n"
            "📞 С вами свяжется администратор для подтверждения записи.\n"
            "⏳ Обычно это занимает не более 30 минут.\n\n"
            "*Спасибо за выбор нашего салона!* 💖",
            reply_markup=main_menu(),
            parse_mode='Markdown'
        )
    else:
        await message.answer(
            "❌ Не удалось создать запись. Пожалуйста, начните заново.",
            reply_markup=main_menu()
        )

    session.close()
    await state.clear()

# ==================== АДМИН-ФУНКЦИОНАЛ ====================

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return

    data = callback.data
    session = Session()

    if data == "admin_pending":
        appointments = session.query(Appointment).filter_by(status="pending").all()

        if not appointments:
            await callback.message.edit_text(
                "✅ Нет заявок на рассмотрении!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
                ])
            )
            session.close()
            return

        text = "📝 *Заявки на рассмотрении:*\n\n"
        for app in appointments:
            user = session.query(User).filter_by(user_id=app.user_id).first()
            service = config.SERVICES.get(app.service, {}).get('name', app.service)

            text += f"🔹 *ID {app.id}*\n"
            text += f"👤 {user.first_name if user else 'Неизвестно'}\n"
            text += f"📱 {user.phone if user and user.phone else 'Нет телефона'}\n"
            text += f"💅 {service}\n"
            text += f"📅 {app.date} в {app.time}\n"
            text += "──────────────\n"

        builder = InlineKeyboardBuilder()
        for app in appointments:
            builder.button(text=f"Рассмотреть #{app.id}", callback_data=f"show_app_{app.id}")
        builder.button(text="🔙 Назад", callback_data="back_to_admin")
        builder.adjust(1)

        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode='Markdown'
        )

    elif data == "admin_stats":
        total_users = session.query(User).count()
        total_appointments = session.query(Appointment).count()
        pending_appointments = session.query(Appointment).filter_by(status="pending").count()
        approved_appointments = session.query(Appointment).filter_by(status="approved").count()

        # Расчет дохода
        appointments = session.query(Appointment).filter_by(status="approved").all()
        total_income = 0
        for app in appointments:
            service = config.SERVICES.get(app.service, {})
            total_income += service.get('price', 0)

        avg_check = total_income // approved_appointments if approved_appointments > 0 else 0

        text = f"""
📊 *Статистика салона:*

👥 Всего клиентов: *{total_users}*
📅 Всего записей: *{total_appointments}*
⏳ Ожидают подтверждения: *{pending_appointments}*
✅ Подтверждено: *{approved_appointments}*

💸 *Доход (подтвержденные):*
💰 Общий доход: *{total_income}* руб.
📈 Средний чек: *{avg_check}* руб.
        """

        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="back_to_admin")

        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode='Markdown'
        )

    elif data == "admin_all_appointments":
        appointments = session.query(Appointment).order_by(Appointment.date.desc()).limit(20).all()

        if not appointments:
            await callback.message.edit_text("📅 Нет записей!")
            session.close()
            return

        text = "📅 *Последние 20 записей:*\n\n"
        for app in appointments:
            user = session.query(User).filter_by(user_id=app.user_id).first()
            service = config.SERVICES.get(app.service, {}).get('name', app.service)
            status_icon = "⏳" if app.status == "pending" else "✅" if app.status == "approved" else "❌"

            text += f"{status_icon} *ID {app.id}*\n"
            text += f"👤 {user.first_name if user else 'Неизвестно'}\n"
            text += f"💅 {service} - {app.date} {app.time}\n"
            text += f"📞 {user.phone if user and user.phone else 'Нет телефона'}\n"
            text += f"🔸 Статус: {app.status}\n"
            text += "──────────────\n"

        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="back_to_admin")

        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode='Markdown'
        )

    elif data == "admin_add_photo":
        await callback.message.edit_text(
            "🖼️ *Добавление фото в галерею*\n\n"
            "Пришлите фото и укажите тип через пробел:\n"
            "• manicure - для маникюра\n"
            "• pedicure - для педикюра\n"
            "• combo - для комбо\n\n"
            "*Пример:* manicure",
            parse_mode='Markdown'
        )

    elif data == "admin_broadcast":
        await callback.message.edit_text(
            "📢 *Рассылка сообщений*\n\n"
            "Введите сообщение для рассылки всем пользователям:",
            parse_mode='Markdown'
        )

    elif data == "back_to_admin":
        await callback.message.edit_text(
            "👑 *Панель администратора*",
            reply_markup=admin_menu(),
            parse_mode='Markdown'
        )

    session.close()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_appointment(callback: CallbackQuery):
    appointment_id = int(callback.data.split("_")[1])

    session = Session()
    appointment = session.query(Appointment).filter_by(id=appointment_id).first()

    if appointment:
        appointment.status = "approved"
        session.commit()

        # Уведомляем клиента
        try:
            user = session.query(User).filter_by(user_id=appointment.user_id).first()
            service = config.SERVICES.get(appointment.service, {}).get('name', appointment.service)

            await bot.send_message(
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
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

        await callback.answer(f"✅ Запись #{appointment_id} одобрена!")
        await callback.message.edit_text(
            f"✅ Запись #{appointment_id} одобрена!\nКлиент уведомлен.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_pending")]
            ])
        )
    else:
        await callback.answer("❌ Запись не найдена!")

    session.close()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_appointment(callback: CallbackQuery):
    appointment_id = int(callback.data.split("_")[1])

    session = Session()
    appointment = session.query(Appointment).filter_by(id=appointment_id).first()

    if appointment:
        appointment.status = "rejected"
        session.commit()

        # Уведомляем клиента
        try:
            await bot.send_message(
                chat_id=appointment.user_id,
                text="😔 *К сожалению, администратор отклонил вашу запись.*\n\n"
                     "Пожалуйста, выберите другое время или свяжитесь с нами для уточнения деталей.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

        await callback.answer(f"❌ Запись #{appointment_id} отклонена!")
        await callback.message.edit_text(
            f"❌ Запись #{appointment_id} отклонена!\nКлиент уведомлен.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_pending")]
            ])
        )
    else:
        await callback.answer("❌ Запись не найдена!")

    session.close()

# ==================== ОБРАБОТКА ФОТО ====================

@dp.message(F.photo)
async def handle_photo(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return

    if not message.caption:
        await message.answer("❌ Укажите тип фото в подписи (manicure/pedicure/combo)")
        return

    caption_parts = message.caption.strip().split()
    if not caption_parts:
        await message.answer("❌ Укажите тип фото (manicure/pedicure/combo)")
        return

    service_type = caption_parts[0].lower()
    if service_type not in ['manicure', 'pedicure', 'combo']:
        await message.answer("❌ Неверный тип. Используйте: manicure, pedicure или combo")
        return

    # Скачиваем фото
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_path = file_info.file_path

    # Создаем директорию для фото, если её нет
    os.makedirs("images", exist_ok=True)

    # Сохраняем фото
    filename = f"images/{service_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

    try:
        await bot.download_file(file_path, filename)

        # Сохраняем в БД
        session = Session()
        service_image = ServiceImage(
            service_type=service_type,
            image_path=filename
        )
        session.add(service_image)
        session.commit()
        session.close()

        await message.answer(
            f"✅ Фото добавлено в галерею ({service_type})!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения фото: {e}")
        await message.answer("❌ Ошибка при сохранении фото!")

# ==================== ОБРАБОТКА ОСТАЛЬНЫХ СООБЩЕНИЙ ====================

@dp.message()
async def handle_text(message: Message):
    text = message.text

    # Если это вопрос для админов (длинное сообщение)
    if len(text) > 10 and message.from_user.id not in config.ADMIN_IDS:
        # Пересылаем админам
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 *Вопрос от клиента:*\n\n{text}\n\n👤 *От:* {message.from_user.full_name}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")

        await message.answer(
            "💌 *Ваше сообщение отправлено администраторам!*\n\n"
            "Они ответят вам в ближайшее время. Обычно это занимает не более 15 минут! ⏳",
            reply_markup=main_menu(),
            parse_mode='Markdown'
        )
        return

    # Если админ отправляет рассылку
    if message.from_user.id in config.ADMIN_IDS and len(text) > 5:
        # Простая проверка - если сообщение длинное, это может быть рассылка
        # В реальном боте лучше сделать отдельное состояние для рассылки
        session = Session()
        users = session.query(User).all()
        session.close()

        success_count = 0
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.user_id,
                    text=f"📢 *Важное сообщение от администрации:*\n\n{text}",
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user.user_id}: {e}")

        await message.answer(f"✅ Рассылка отправлена {success_count} пользователям!")

# ==================== ЗАПУСК БОТА ====================

async def main():
    # Инициализация базы данных
    database.init_db()

    logger.info("🤖 Бот запускается...")

    # Запускаем бота
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == '__main__':
    asyncio.run(main())
