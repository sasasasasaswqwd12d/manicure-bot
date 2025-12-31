import asyncio
import logging
import os
import random
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardRemove,
    FSInputFile, Contact, Location, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.markdown import hbold, hitalic, hlink

import config
from database import Session, User, Appointment, ServiceImage, Review, UserDiscount, Reminder, AdminMessage, init_db
import keyboards as kb

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Создаем папки
Path("images/reviews").mkdir(parents=True, exist_ok=True)
Path("images/gallery").mkdir(parents=True, exist_ok=True)

# Состояния
class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()
    applying_discount = State()
    getting_contact = State()

class ReviewStates(StatesGroup):
    choosing_rating = State()
    writing_text = State()
    waiting_for_photo = State()

class ProfileStates(StatesGroup):
    setting_birthday = State()

class AdminStates(StatesGroup):
    broadcast_all = State()
    broadcast_filtered = State()
    broadcast_single = State()
    adding_photo = State()
    managing_review = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def save_user(telegram_user: types.User, phone: str = None) -> User:
    """Сохраняет или обновляет пользователя в БД"""
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_user.id).first()

        if not user:
            # Создаем нового пользователя
            referral_code = kb.generate_referral_code()
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                phone=phone,
                referral_code=referral_code,
                discount_percent=0
            )
            session.add(user)
            session.commit()

            # Создаем скидку на первую запись
            discount = UserDiscount(
                user_id=user.id,
                discount_type='first_visit',
                discount_percent=config.LOYALTY_SYSTEM['first_visit_discount'],
                valid_until=datetime.now() + timedelta(days=30)
            )
            session.add(discount)
            session.commit()

            logger.info(f"Создан новый пользователь: {user.id} ({user.first_name})")
        elif phone:
            # Обновляем телефон если изменился
            user.phone = phone
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            session.commit()

        return user
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")
        session.rollback()
        return None
    finally:
        session.close()

async def notify_admins(appointment: Appointment, user: User):
    """Отправляет уведомление администраторам о новой записи"""
    admin_message = f"""
🚨 НОВАЯ ЗАПИСЬ #{appointment.id}

👤 Клиент: {user.first_name} {user.last_name or ''}
📱 Телефон: {user.phone or 'Не указан'}
👤 TG: @{user.username or 'нет'}
🎫 Визитов: {user.visits_count}
🎁 Скидка: {user.discount_percent}%

💅 Услуга: {appointment.service_name}
💰 Цена: {appointment.final_price}₽ (скидка {appointment.discount_applied}%)
📅 Дата: {appointment.date}
⏰ Время: {appointment.time}

🕐 Создано: {appointment.created_at.strftime('%H:%M')}
📍 Адрес: {config.SALON_INFO['address']}
    """

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_message,
                reply_markup=kb.admin_appointment_actions(appointment.id)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

async def schedule_reminders(appointment: Appointment):
    """Планирует напоминания о записи"""
    if not config.REMINDERS['24_hours'] and not config.REMINDERS['3_hours']:
        return

    session = Session()
    try:
        # Парсим дату и время записи
        appointment_datetime = datetime.strptime(f"{appointment.date} {appointment.time}", "%d.%m.%Y %H:%M")

        # Напоминание за 24 часа
        if config.REMINDERS['24_hours']:
            reminder_24h = Reminder(
                user_id=appointment.user_id,
                appointment_id=appointment.id,
                reminder_type='24h_before',
                scheduled_for=appointment_datetime - timedelta(hours=24)
            )
            session.add(reminder_24h)

        # Напоминание за 3 часа
        if config.REMINDERS['3_hours']:
            reminder_3h = Reminder(
                user_id=appointment.user_id,
                appointment_id=appointment.id,
                reminder_type='3h_before',
                scheduled_for=appointment_datetime - timedelta(hours=3)
            )
            session.add(reminder_3h)

        session.commit()
    except Exception as e:
        logger.error(f"Ошибка планирования напоминаний: {e}")
        session.rollback()
    finally:
        session.close()

async def send_reminder(reminder: Reminder):
    """Отправляет напоминание пользователю"""
    session = Session()
    try:
        appointment = session.query(Appointment).filter_by(id=reminder.appointment_id).first()
        user = session.query(User).filter_by(id=reminder.user_id).first()

        if not appointment or appointment.status != 'confirmed':
            return

        if reminder.reminder_type == '24h_before':
            message = f"""
🔔 Напоминание о записи #{appointment.id}

💅 Услуга: {appointment.service_name}
📅 Завтра в {appointment.time}
📍 Адрес: {config.SALON_INFO['address']}

📞 Телефон салона: {config.SALON_INFO['phone']}

⚠️ Пожалуйста, подтвердите, что придете!
            """
        elif reminder.reminder_type == '3h_before':
            message = f"""
⏰ Скоро ваш визит!

Через 3 часа: {appointment.service_name}
📍 {config.SALON_INFO['address']}

📞 {config.SALON_INFO['phone']}
            """

        await bot.send_message(user.telegram_id, message)
        reminder.sent_at = datetime.now()
        session.commit()

    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")
    finally:
        session.close()

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    user = await save_user(message.from_user)

    welcome_text = f"""
✨ {hbold('Добро пожаловать в Nail Studio!')} ✨

📍 {hbold('Мы находимся в Мытищах:')}
{config.SALON_INFO['address']}

💅 {hitalic('Я помогу вам записаться на маникюр, педикюр или комплексные услуги')}

🎁 {hbold('Система скидок:')}
• Первая запись: {config.LOYALTY_SYSTEM['first_visit_discount']}%
• Приведи друга: {config.LOYALTY_SYSTEM['referral_bonus']}%
• День рождения: {config.LOYALTY_SYSTEM['birthday_discount']}%

Выберите действие в меню ниже 👇
    """

    await message.answer(welcome_text, reply_markup=kb.main_menu(), parse_mode='HTML')

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Панель администратора"""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return

    session = Session()
    try:
        # Статистика
        total_users = session.query(User).count()
        total_appointments = session.query(Appointment).count()
        pending_appointments = session.query(Appointment).filter_by(status="pending").count()
        today_appointments = session.query(Appointment).filter(
            Appointment.date == datetime.now().strftime("%d.%m.%Y"),
            Appointment.status.in_(["confirmed", "pending"])
        ).count()

        stats_text = f"""
👑 Панель администратора

📊 {hbold('Статистика:')}
👥 Пользователей: {total_users}
📅 Всего записей: {total_appointments}
⏳ Ожидают подтверждения: {pending_appointments}
📌 На сегодня: {today_appointments}
        """

        await message.answer(stats_text, reply_markup=kb.admin_menu_keyboard(), parse_mode='HTML')
    finally:
        session.close()

# ==================== ГЛАВНОЕ МЕНЮ ====================

@dp.message(F.text == "💅 Услуги и цены")
async def show_services(message: Message):
    """Показывает услуги и цены"""
    services_text = f"""
💅 {hbold('Наши услуги и цены:')}

"""
    for service_id, service in config.SERVICES.items():
        description = f" ({service['description']})" if 'description' in service else ""
        duration = f" ⏱️ {service['duration']} мин" if 'duration' in service else ""
        services_text += f"{service['emoji']} {hbold(service['name'])}{description}\n"
        services_text += f"   💰 {service['price']}₽{duration}\n\n"

    services_text += f"\n📍 {config.SALON_INFO['address']}"
    services_text += f"\n⏰ {config.SALON_INFO['working_hours']}"

    await message.answer(services_text, reply_markup=kb.services_menu(), parse_mode='HTML')

@dp.message(F.text == "🖼️ Галерея работ")
async def show_gallery(message: Message):
    """Показывает галерею работ"""
    await message.answer(
        "🖼️ Галерея наших работ\n\n"
        "Выберите категорию для просмотра:",
        reply_markup=kb.gallery_keyboard()
    )

@dp.message(F.text == "📅 Записаться онлайн")
async def start_booking(message: Message, state: FSMContext):
    """Начинает процесс записи"""
    await state.set_state(BookingStates.choosing_service)
    await show_services(message)

@dp.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    """Показывает профиль пользователя"""
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        # Получаем ближайшие записи
        upcoming_appointments = session.query(Appointment).filter(
            Appointment.user_id == user.id,
            Appointment.status.in_(["pending", "confirmed"])
        ).order_by(Appointment.date).limit(3).all()

        # Получаем доступные скидки
        available_discounts = kb.get_discounts_for_user(user)

        profile_text = f"""
👤 {hbold('Ваш профиль')}

📋 {hbold('Информация:')}
👤 Имя: {user.first_name} {user.last_name or ''}
📱 Телефон: {user.phone or 'Не указан'}
🎫 Визитов: {user.visits_count}
💰 Всего потрачено: {user.total_spent}₽
🎁 Текущая скидка: {user.discount_percent}%

🎫 {hbold('Реферальный код:')}
Пригласите друга: {user.referral_code}
Вы оба получите {config.LOYALTY_SYSTEM['referral_bonus']}% скидку!

🎁 {hbold('Доступные скидки:')}
"""

        for discount in available_discounts:
            profile_text += f"• {discount['name']}: {discount['percent']}%\n"

        if not available_discounts:
            profile_text += "Пока нет доступных скидок\n"

        if upcoming_appointments:
            profile_text += f"\n📅 {hbold('Ближайшие записи:')}\n"
            for app in upcoming_appointments:
                status_icon = "⏳" if app.status == "pending" else "✅"
                profile_text += f"{status_icon} {app.date} {app.time} - {app.service_name}\n"

        await message.answer(profile_text, reply_markup=kb.profile_keyboard(), parse_mode='HTML')

    finally:
        session.close()

@dp.message(F.text == "⭐ Отзывы")
async def show_reviews_menu(message: Message):
    """Показывает меню отзывов"""
    session = Session()
    try:
        total_reviews = session.query(Review).filter_by(is_approved=True).count()

        reviews_text = f"""
⭐ {hbold('Отзывы наших клиентов')}

Всего отзывов: {total_reviews}

💖 Только реальные отзывы от наших клиентов.
Оставляйте свои впечатления и фотографии работ!
        """

        await message.answer(reviews_text, reply_markup=kb.review_keyboard(), parse_mode='HTML')
    finally:
        session.close()

@dp.message(F.text == "📞 Контакты")
async def show_contacts(message: Message):
    """Показывает контакты"""
    contacts_text = f"""
📞 {hbold('Свяжитесь с нами')}

📍 {hbold('Адрес:')}
{config.SALON_INFO['address']}
{config.SALON_INFO['metro']}

📱 {hbold('Телефон:')}
{config.SALON_INFO['phone']}

⏰ {hbold('Часы работы:')}
{config.SALON_INFO['working_hours']}

Мы ответим в течение 15 минут!
    """

    await message.answer(contacts_text, reply_markup=kb.contact_keyboard(), parse_mode='HTML')

@dp.message(F.text == "💖 О нас")
async def show_about(message: Message):
    """Показывает информацию о салоне"""
    about_text = f"""
💖 {hbold('О нас')}

Nail Studio - это место, где рождается красота!

🌟 {hbold('Наша миссия:')} делать мир красивее, одну улыбку за раз!

🎯 {hbold('Наши принципы:')}
• Качество выше всего
• Индивидуальный подход к каждому
• Постоянное обучение новым техникам
• Только безопасные материалы

🏆 {hbold('Наши достижения:')}
• 1000+ довольных клиентов
• 98% клиентов возвращаются к нам

Ждем вас в нашем уютном салоне! 💅✨
    """

    await message.answer(about_text, parse_mode='HTML')

# ==================== ПРОЦЕСС ЗАПИСИ ====================

@dp.callback_query(F.data == "book_now")
async def book_now(callback: CallbackQuery, state: FSMContext):
    """Начинает запись"""
    await state.set_state(BookingStates.choosing_service)
    await show_services(callback.message)

@dp.callback_query(F.data.startswith("service_"), BookingStates.choosing_service)
async def choose_service(callback: CallbackQuery, state: FSMContext):
    """Выбор услуги"""
    service_id = callback.data.split("_")[1]
    service = config.SERVICES[service_id]

    await state.update_data(
        service_id=service_id,
        service_name=service['name'],
        original_price=service['price'],
        duration=service.get('duration', 60)
    )

    await state.set_state(BookingStates.choosing_date)

    await callback.message.edit_text(
        f"✅ Выбрано: {service['emoji']} {hbold(service['name'])} - {service['price']}₽\n\n"
        f"📅 Теперь выберите дату:",
        reply_markup=kb.booking_dates_keyboard(),
        parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("date_"), BookingStates.choosing_date)
async def choose_date(callback: CallbackQuery, state: FSMContext):
    """Выбор даты"""
    date_str = callback.data.split("_")[1]
    await state.update_data(date=date_str)
    await state.set_state(BookingStates.choosing_time)

    await callback.message.edit_text(
        f"📅 Дата: {hbold(date_str)}\n\n"
        f"⏰ Выберите удобное время:",
        reply_markup=kb.booking_times_keyboard(),
        parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("time_"), BookingStates.choosing_time)
async def choose_time(callback: CallbackQuery, state: FSMContext):
    """Выбор времени"""
    time_slot = callback.data.split("_")[1]
    await state.update_data(time=time_slot)
    await state.set_state(BookingStates.confirming)

    data = await state.get_data()

    summary = f"""
📋 {hbold('Ваша заявка на запись:')}

💅 Услуга: {data['service_name']}
💰 Базовая цена: {data['original_price']}₽
📅 Дата: {data['date']}
⏰ Время: {time_slot}
⏱️ Длительность: {data.get('duration', 60)} мин

🎁 {hitalic('У вас есть доступные скидки!')}

{hitalic('Всё верно?')}
    """

    await callback.message.edit_text(
        summary,
        reply_markup=kb.confirm_booking_keyboard(),
        parse_mode='HTML'
    )

@dp.callback_query(F.data == "confirm_booking", BookingStates.confirming)
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Подтверждение записи и запрос контакта"""
    await callback.message.edit_text(
        "✅ Отлично! Почти готово!\n\n"
        "📱 Теперь поделитесь своим номером телефона, "
        "чтобы администратор мог с вами связаться:"
    )

    await callback.message.answer(
        "Нажмите кнопку ниже:",
        reply_markup=kb.share_contact_keyboard()
    )

    await state.set_state(BookingStates.getting_contact)

@dp.callback_query(F.data == "apply_discount")
async def apply_discount(callback: CallbackQuery, state: FSMContext):
    """Применение скидки к записи"""
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        available_discounts = kb.get_discounts_for_user(user)

        if not available_discounts:
            await callback.answer("🎫 У вас нет доступных скидок", show_alert=True)
            return

        await state.set_state(BookingStates.applying_discount)

        discounts_text = "🎁 Доступные скидки:\n\n"
        for discount in available_discounts:
            discounts_text += f"• {discount['name']}: {discount['percent']}%\n"

        await callback.message.edit_text(
            discounts_text,
            reply_markup=kb.discount_keyboard(available_discounts)
        )

    finally:
        session.close()

@dp.callback_query(F.data.startswith("use_discount_"), BookingStates.applying_discount)
async def use_selected_discount(callback: CallbackQuery, state: FSMContext):
    """Применение выбранной скидки"""
    discount_id = callback.data.split("_")[2]
    data = await state.get_data()

    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        available_discounts = kb.get_discounts_for_user(user)

        selected_discount = next((d for d in available_discounts if d['id'] == discount_id), None)

        if not selected_discount:
            await callback.answer("❌ Скидка не найдена", show_alert=True)
            return

        # Рассчитываем цену со скидкой
        original_price = data['original_price']
        discount_percent = selected_discount['percent']
        final_price = int(original_price * (1 - discount_percent / 100))

        await state.update_data(
            discount_id=discount_id,
            discount_percent=discount_percent,
            final_price=final_price
        )

        summary = f"""
📋 {hbold('Заявка со скидкой:')}

💅 Услуга: {data['service_name']}
💰 Базовая цена: {original_price}₽
🎁 Скидка: {selected_discount['name']} ({discount_percent}%)
✅ Итоговая цена: {final_price}₽
📅 Дата: {data['date']}
⏰ Время: {data['time']}

{hitalic('Всё верно?')}
        """

        await callback.message.edit_text(
            summary,
            reply_markup=kb.confirm_booking_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(BookingStates.confirming)

    finally:
        session.close()

@dp.callback_query(F.data == "no_discount", BookingStates.applying_discount)
async def no_discount(callback: CallbackQuery, state: FSMContext):
    """Отказ от применения скидки"""
    data = await state.get_data()

    summary = f"""
📋 {hbold('Ваша заявка на запись:')}

💅 Услуга: {data['service_name']}
💰 Цена: {data['original_price']}₽
📅 Дата: {data['date']}
⏰ Время: {data['time']}

{hitalic('Всё верно?')}
    """

    await callback.message.edit_text(
        summary,
        reply_markup=kb.confirm_booking_keyboard(),
        parse_mode='HTML'
    )
    await state.set_state(BookingStates.confirming)

@dp.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Отмена записи"""
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена")
    await callback.message.answer("Вы вернулись в главное меню", reply_markup=kb.main_menu())

# ==================== ОБРАБОТКА КОНТАКТА ====================

@dp.message(F.contact, BookingStates.getting_contact)
async def process_contact(message: Message, state: FSMContext):
    """Обработка полученного контакта и сохранение записи"""
    try:
        # Сохраняем пользователя с телефоном
        user = await save_user(message.from_user, message.contact.phone_number)

        if not user:
            await message.answer("❌ Ошибка сохранения. Попробуйте снова.", reply_markup=kb.main_menu())
            await state.clear()
            return

        # Получаем данные записи
        data = await state.get_data()

        # Рассчитываем окончательную цену
        final_price = data.get('final_price', data['original_price'])
        discount_percent = data.get('discount_percent', 0)

        # Сохраняем запись в БД
        session = Session()
        try:
            appointment = Appointment(
                user_id=user.id,
                service=data['service_id'],
                service_name=data['service_name'],
                original_price=data['original_price'],
                final_price=final_price,
                discount_applied=discount_percent,
                date=data['date'],
                time=data['time'],
                status="pending"
            )
            session.add(appointment)
            session.commit()

            # Если была применена скидка, помечаем ее как использованную
            if data.get('discount_id'):
                if data['discount_id'] == 'first_visit':
                    discount = session.query(UserDiscount).filter_by(
                        user_id=user.id,
                        discount_type='first_visit',
                        is_used=False
                    ).first()
                    if discount:
                        discount.is_used = True
                # Обновляем общий процент скидки пользователя
                user.discount_percent = max(user.discount_percent, discount_percent)
                session.commit()

            # Планируем напоминания
            await schedule_reminders(appointment)

            # Отправляем уведомление админам
            await notify_admins(appointment, user)

            # Подтверждаем пользователю
            success_text = f"""
✅ {hbold('Заявка успешно создана!')}

📝 Номер заявки: #{appointment.id}
💅 Услуга: {data['service_name']}
💰 Цена: {final_price}₽ (скидка {discount_percent}%)
📅 Дата: {data['date']}
⏰ Время: {data['time']}

📞 Администратор свяжется с вами в течение 30 минут
для подтверждения записи.

📍 Адрес: {config.SALON_INFO['address']}
📞 Телефон: {config.SALON_INFO['phone']}

Спасибо за выбор Nail Studio! 💖
            """

            await message.answer(
                success_text,
                reply_markup=kb.main_menu(),
                parse_mode='HTML'
            )

        except Exception as e:
            logger.error(f"Ошибка сохранения записи: {e}")
            await message.answer("❌ Ошибка при создании заявки. Попробуйте снова.")
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Ошибка обработки контакта: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")
    finally:
        await state.clear()

# ==================== ПРОФИЛЬ И МОИ ЗАПИСИ ====================

@dp.callback_query(F.data == "my_appointments")
async def show_my_appointments(callback: CallbackQuery):
    """Показывает записи пользователя"""
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        appointments = session.query(Appointment).filter_by(user_id=user.id)\
            .order_by(Appointment.date.desc()).limit(10).all()

        if not appointments:
            await callback.message.edit_text(
                "📭 У вас пока нет записей\n\n"
                "Запишитесь на услугу через меню 💅",
                reply_markup=kb.profile_keyboard()
            )
            return

        appointments_text = f"""
📋 {hbold('Ваши записи:')}

"""
        for app in appointments:
            status_icons = {
                "pending": "⏳",
                "confirmed": "✅",
                "completed": "🎉",
                "cancelled": "❌",
                "noshow": "🚫"
            }
            status_icon = status_icons.get(app.status, "📝")

            appointments_text += f"""
{status_icon} #{app.id} - {app.date} {app.time}
💅 {app.service_name}
💰 {app.final_price}₽ (скидка {app.discount_applied}%)
📊 Статус: {app.status}
──────────────
"""

        await callback.message.edit_text(
            appointments_text,
            reply_markup=kb.profile_keyboard(),
            parse_mode='HTML'
        )

    finally:
        session.close()

@dp.callback_query(F.data == "my_discounts")
async def show_my_discounts(callback: CallbackQuery):
    """Показывает скидки пользователя"""
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        available_discounts = kb.get_discounts_for_user(user)
        used_discounts = session.query(UserDiscount).filter_by(user_id=user.id, is_used=True).all()

        discounts_text = f"""
🎁 {hbold('Ваши скидки:')}

🎫 {hbold('Доступные:')}
"""

        if available_discounts:
            for discount in available_discounts:
                discounts_text += f"• {discount['name']}: {discount['percent']}%\n"
        else:
            discounts_text += "Нет доступных скидок\n"

        discounts_text += f"\n📋 {hbold('Использованные:')}\n"

        if used_discounts:
            for discount in used_discounts:
                discounts_text += f"• {discount.discount_type}: {discount.discount_percent}%\n"
        else:
            discounts_text += "Вы еще не использовали скидки\n"

        discounts_text += f"\n🎫 {hbold('Реферальный код:')}\n{user.referral_code}"
        discounts_text += f"\nПригласите друга и получите {config.LOYALTY_SYSTEM['referral_bonus']}% скидку!"

        await callback.message.edit_text(
            discounts_text,
            reply_markup=kb.profile_keyboard(),
            parse_mode='HTML'
        )

    finally:
        session.close()

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_my_appointment(callback: CallbackQuery):
    """Отмена записи пользователем"""
    try:
        appointment_id = int(callback.data.split("_")[1])
        session = Session()

        try:
            user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
            appointment = session.query(Appointment).filter_by(id=appointment_id, user_id=user.id).first()

            if not appointment:
                await callback.answer("❌ Запись не найдена", show_alert=True)
                return

            # Можно отменять только pending и confirmed записи
            if appointment.status not in ["pending", "confirmed"]:
                await callback.answer(f"❌ Нельзя отменить запись со статусом {appointment.status}", show_alert=True)
                return

            appointment.status = "cancelled"
            appointment.cancelled_at = datetime.now()
            session.commit()

            # Уведомляем админов
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"⚠️ Отмена записи #{appointment_id}\n\n"
                        f"Клиент: {user.first_name}\n"
                        f"Услуга: {appointment.service_name}\n"
                        f"Дата: {appointment.date} {appointment.time}"
                    )
                except:
                    pass

            await callback.answer("✅ Запись отменена", show_alert=True)
            await show_my_appointments(callback)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Ошибка отмены записи: {e}")
        await callback.answer("❌ Ошибка отмены", show_alert=True)

@dp.callback_query(F.data.startswith("reschedule_"))
async def reschedule_appointment(callback: CallbackQuery, state: FSMContext):
    """Перенос записи"""
    try:
        appointment_id = int(callback.data.split("_")[1])
        session = Session()

        try:
            user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
            appointment = session.query(Appointment).filter_by(id=appointment_id, user_id=user.id).first()

            if not appointment:
                await callback.answer("❌ Запись не найдена", show_alert=True)
                return

            # Сохраняем данные записи для переноса
            await state.update_data(
                reschedule_appointment_id=appointment_id,
                service_id=appointment.service,
                service_name=appointment.service_name,
                original_price=appointment.original_price,
                final_price=appointment.final_price
            )

            # Показываем выбор новой даты
            await state.set_state(BookingStates.choosing_date)
            await callback.message.edit_text(
                f"🔄 Перенос записи #{appointment_id}\n\n"
                f"📅 Выберите новую дату:",
                reply_markup=kb.booking_dates_keyboard()
            )

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Ошибка переноса записи: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# ==================== ОТЗЫВЫ С ФОТО ====================

@dp.callback_query(F.data == "leave_review")
async def start_review(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс оставления отзыва"""
    await state.set_state(ReviewStates.choosing_rating)
    await callback.message.edit_text(
        "⭐ Оцените нашу работу:\n\n"
        "Выберите количество звезд от 1 до 5:",
        reply_markup=kb.rating_keyboard()
    )

@dp.callback_query(F.data == "leave_review_with_photo")
async def start_review_with_photo(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс оставления отзыва с фото"""
    await state.set_state(ReviewStates.choosing_rating)
    await state.update_data(with_photo=True)
    await callback.message.edit_text(
        "📸 Отзыв с фото\n\n"
        "Сначала оцените нашу работу (1-5 звезд):",
        reply_markup=kb.rating_keyboard()
    )

@dp.callback_query(F.data.startswith("rate_"))
async def choose_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора рейтинга"""
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)

    data = await state.get_data()

    if data.get('with_photo'):
        await state.set_state(ReviewStates.waiting_for_photo)
        await callback.message.edit_text(
            f"✅ Вы поставили {rating} звезд!\n\n"
            f"Теперь отправьте фото вашего маникюра:"
        )
    else:
        await state.set_state(ReviewStates.writing_text)
        await callback.message.edit_text(
            f"✅ Вы поставили {rating} звезд!\n\n"
            f"Теперь напишите ваш отзыв (можно несколько предложений):\n\n"
            f"{hitalic('Напишите "отмена" чтобы отменить')}",
            parse_mode='HTML'
        )

@dp.message(ReviewStates.waiting_for_photo)
async def process_review_photo(message: Message, state: FSMContext):
    """Обработка фото для отзыва"""
    if message.photo:
        # Сохраняем фото
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_ext = file_info.file_path.split('.')[-1]

        # Создаем уникальное имя файла
        filename = f"images/reviews/review_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
        await bot.download_file(file_info.file_path, filename)

        await state.update_data(photo_path=filename)
        await state.set_state(ReviewStates.writing_text)

        await message.answer(
            "📸 Фото сохранено!\n\n"
            "Теперь напишите ваш отзыв (можно несколько предложений):\n\n"
            f"{hitalic('Напишите "отмена" чтобы отменить')}",
            parse_mode='HTML'
        )
    else:
        await message.answer("Пожалуйста, отправьте фото вашего маникюра")

@dp.message(ReviewStates.writing_text)
async def process_review_text(message: Message, state: FSMContext):
    """Обработка текста отзыва"""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отмена отзыва", reply_markup=kb.main_menu())
        return

    data = await state.get_data()

    if not data.get('rating'):
        await message.answer("❌ Сначала выберите рейтинг")
        await state.clear()
        return

    # Сохраняем отзыв
    session = Session()
    try:
        user = await save_user(message.from_user)

        review = Review(
            user_id=user.id,
            rating=data['rating'],
            text=message.text,
            photo_path=data.get('photo_path'),
            is_approved=True
        )
        session.add(review)
        session.commit()

        # Уведомляем админов
        for admin_id in config.ADMIN_IDS:
            try:
                admin_msg = f"""
⭐ Новый отзыв!

👤 От: {user.first_name}
⭐ Оценка: {'⭐' * data['rating']}
📝 Текст: {message.text}
"""
                if data.get('photo_path'):
                    await bot.send_photo(
                        admin_id,
                        photo=FSInputFile(data['photo_path']),
                        caption=admin_msg
                    )
                else:
                    await bot.send_message(admin_id, admin_msg)
            except Exception as e:
                logger.error(f"Ошибка уведомления админа: {e}")

        await message.answer(
            f"✅ {hbold('Спасибо за ваш отзыв!')}\n\n"
            f"Ваше мнение очень важно для нас 💖",
            reply_markup=kb.main_menu(),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Ошибка сохранения отзыва: {e}")
        await message.answer("❌ Ошибка сохранения отзыва")
    finally:
        session.close()
        await state.clear()

@dp.callback_query(F.data == "read_reviews")
async def show_all_reviews(callback: CallbackQuery):
    """Показывает все отзывы"""
    session = Session()
    try:
        reviews = session.query(Review).filter_by(is_approved=True)\
            .order_by(Review.created_at.desc()).limit(10).all()

        if not reviews:
            await callback.message.edit_text(
                "📝 Отзывов пока нет. Будьте первым!",
                reply_markup=kb.review_keyboard()
            )
            return

        for review in reviews:
            user = session.query(User).filter_by(id=review.user_id).first()
            name = user.first_name if user else "Аноним"
            date = review.created_at.strftime("%d.%m.%Y")

            review_text = f"""
{'⭐' * review.rating} {hbold(name)} ({date}):

{review.text}
"""

            if review.photo_path and os.path.exists(review.photo_path):
                try:
                    await callback.message.answer_photo(
                        FSInputFile(review.photo_path),
                        caption=review_text,
                        parse_mode='HTML'
                    )
                except:
                    await callback.message.answer(
                        review_text,
                        parse_mode='HTML'
                    )
            else:
                await callback.message.answer(
                    review_text,
                    parse_mode='HTML'
                )

        await callback.message.answer(
            f"📊 Всего отзывов: {len(reviews)}",
            reply_markup=kb.review_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка загрузки отзывов: {e}")
        await callback.answer("❌ Ошибка загрузки отзывов", show_alert=True)
    finally:
        session.close()

# ==================== АДМИН-ПАНЕЛЬ ====================

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка админ-колбэков"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return

    data = callback.data

    if data == "admin_pending":
        await show_pending_appointments(callback)

    elif data == "admin_broadcast":
        await callback.message.edit_text(
            "📢 Индивидуальная рассылка\n\n"
            "Выберите тип рассылки:",
            reply_markup=kb.admin_broadcast_keyboard()
        )

    elif data == "broadcast_all":
        await state.set_state(AdminStates.broadcast_all)
        await callback.message.edit_text(
            "📢 Рассылка всем пользователям\n\n"
            "Введите сообщение для рассылки:"
        )

    elif data.startswith("admin_approve_"):
        await approve_appointment(callback)

    elif data.startswith("admin_reject_"):
        await reject_appointment(callback)

@dp.message(AdminStates.broadcast_all)
async def process_broadcast_all(message: Message, state: FSMContext):
    """Обработка рассылки всем пользователям"""
    session = Session()
    try:
        users = session.query(User).all()
        success_count = 0

        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"📢 Сообщение от салона:\n\n{message.text}"
                )
                success_count += 1
            except:
                pass

        # Сохраняем в историю
        admin_msg = AdminMessage(
            admin_id=message.from_user.id,
            message_type='broadcast_all',
            message_text=message.text,
            sent_count=success_count,
            sent_at=datetime.now()
        )
        session.add(admin_msg)
        session.commit()

        await message.answer(
            f"✅ Рассылка отправлена {success_count} пользователям из {len(users)}",
            reply_markup=kb.admin_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")
        await message.answer("❌ Ошибка рассылки")
    finally:
        session.close()
        await state.clear()

async def show_pending_appointments(callback: CallbackQuery):
    """Показывает ожидающие подтверждения записи"""
    session = Session()
    try:
        appointments = session.query(Appointment).filter_by(status="pending")\
            .order_by(Appointment.created_at).all()

        if not appointments:
            await callback.message.edit_text(
                "✅ Нет новых заявок на подтверждение",
                reply_markup=kb.admin_menu_keyboard()
            )
            return

        for appointment in appointments[:5]:
            user = session.query(User).filter_by(id=appointment.user_id).first()

            text = f"""
📝 Заявка #{appointment.id}
👤 {user.first_name} {user.last_name or ''}
📱 {user.phone or 'Нет телефона'}
🎫 Визитов: {user.visits_count}
💅 {appointment.service_name}
💰 {appointment.final_price}₽ (скидка {appointment.discount_applied}%)
📅 {appointment.date} в {appointment.time}
🕐 {appointment.created_at.strftime('%H:%M')}
            """

            await callback.message.answer(
                text,
                reply_markup=kb.admin_appointment_actions(appointment.id)
            )

        await callback.message.answer(
            f"📊 Всего заявок: {len(appointments)}",
            reply_markup=kb.admin_menu_keyboard()
        )

    finally:
        session.close()

async def approve_appointment(callback: CallbackQuery):
    """Подтверждение записи администратором"""
    appointment_id = int(callback.data.split("_")[2])
    session = Session()
    try:
        appointment = session.query(Appointment).filter_by(id=appointment_id).first()
        if appointment:
            appointment.status = "confirmed"
            appointment.confirmed_at = datetime.now()
            session.commit()

            user = session.query(User).filter_by(id=appointment.user_id).first()

            # Увеличиваем счетчик визитов пользователя
            user.visits_count += 1
            user.total_spent += appointment.final_price
            user.last_visit = datetime.now()

            # Проверяем достижения по визитам для скидок
            for milestone, discount in config.LOYALTY_SYSTEM['visit_milestones'].items():
                if user.visits_count == milestone:
                    user.discount_percent = max(user.discount_percent, discount)
                    # Создаем запись о скидке
                    new_discount = UserDiscount(
                        user_id=user.id,
                        discount_type='milestone',
                        discount_percent=discount
                    )
                    session.add(new_discount)

            session.commit()

            # Уведомляем клиента
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"✅ {hbold('Ваша запись подтверждена!')} #{appointment.id}\n\n"
                    f"💅 Услуга: {appointment.service_name}\n"
                    f"💰 Цена: {appointment.final_price}₽\n"
                    f"📅 Дата: {appointment.date}\n"
                    f"⏰ Время: {appointment.time}\n\n"
                    f"📍 {hbold('Адрес:')}\n"
                    f"{config.SALON_INFO['address']}\n\n"
                    f"📞 {hbold('Телефон:')}\n"
                    f"{config.SALON_INFO['phone']}\n\n"
                    f"🎫 Теперь у вас {user.visits_count} визитов!\n"
                    f"🎁 Ваша скидка: {user.discount_percent}%\n\n"
                    f"{hitalic('Ждем вас! Приходите за 5-10 минут до записи.')} 💖",
                    parse_mode='HTML'
                )
            except:
                pass

            await callback.answer("✅ Запись подтверждена!", show_alert=True)
        else:
            await callback.answer("❌ Запись не найдена", show_alert=True)
    finally:
        session.close()

async def reject_appointment(callback: CallbackQuery):
    """Отклонение записи администратором"""
    appointment_id = int(callback.data.split("_")[2])
    session = Session()
    try:
        appointment = session.query(Appointment).filter_by(id=appointment_id).first()
        if appointment:
            appointment.status = "cancelled"
            appointment.cancelled_at = datetime.now()
            session.commit()

            user = session.query(User).filter_by(id=appointment.user_id).first()

            # Уведомляем клиента
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"😔 {hbold('Ваша запись отклонена.')} #{appointment.id}\n\n"
                    f"Пожалуйста, выберите другое время или свяжитесь с нами.\n\n"
                    f"📞 {config.SALON_INFO['phone']}"
                )
            except:
                pass

            await callback.answer("❌ Запись отклонена", show_alert=True)
        else:
            await callback.answer("❌ Запись не найдена", show_alert=True)
    finally:
        session.close()

# ==================== НАВИГАЦИЯ ====================

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text("Главное меню:")
    await callback.message.answer("Выберите действие:", reply_markup=kb.main_menu())

@dp.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    """Возврат к услугам"""
    await state.set_state(BookingStates.choosing_service)
    await show_services(callback.message)

@dp.callback_query(F.data == "back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору даты"""
    await state.set_state(BookingStates.choosing_date)
    data = await state.get_data()

    service = config.SERVICES.get(data.get('service_id', 'manicure'))

    await callback.message.edit_text(
        f"✅ Выбрано: {service['emoji']} {service['name']}\n\n"
        f"📅 Выберите дату:",
        reply_markup=kb.booking_dates_keyboard()
    )

@dp.callback_query(F.data == "back_to_confirmation")
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """Возврат к подтверждению"""
    await state.set_state(BookingStates.confirming)
    data = await state.get_data()

    summary = f"""
📋 {hbold('Ваша заявка на запись:')}

💅 Услуга: {data['service_name']}
💰 Базовая цена: {data['original_price']}₽
📅 Дата: {data['date']}
⏰ Время: {data['time']}

{hitalic('Всё верно?')}
    """

    await callback.message.edit_text(
        summary,
        reply_markup=kb.confirm_booking_keyboard(),
        parse_mode='HTML'
    )

# ==================== СИСТЕМА НАПОМИНАНИЙ ====================

async def check_reminders():
    """Проверяет и отправляет напоминания"""
    session = Session()
    try:
        now = datetime.now()
        reminders = session.query(Reminder).filter(
            Reminder.scheduled_for <= now,
            Reminder.sent_at.is_(None)
        ).all()

        for reminder in reminders:
            await send_reminder(reminder)

    except Exception as e:
        logger.error(f"Ошибка проверки напоминаний: {e}")
    finally:
        session.close()

# ==================== ЗАПУСК БОТА ====================

async def scheduled_tasks():
    """Планировщик задач"""
    while True:
        try:
            await check_reminders()
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")

        await asyncio.sleep(60)  # Проверяем каждую минуту

async def main():
    """Основная функция запуска бота"""
    # Инициализируем БД
    init_db()

    logger.info("🤖 Бот запускается...")

    # Запускаем планировщик задач в фоне
    asyncio.create_task(scheduled_tasks())

    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
