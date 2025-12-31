from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
import config
from datetime import datetime, timedelta
import random
import string

def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="💅 Услуги и цены")
    builder.button(text="🖼️ Галерея работ")
    builder.button(text="📅 Записаться онлайн")
    builder.button(text="👤 Мой профиль")
    builder.button(text="⭐ Отзывы")
    builder.button(text="📞 Контакты")
    builder.button(text="💖 О нас")
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup(resize_keyboard=True)

def services_menu():
    builder = InlineKeyboardBuilder()
    for service_id, service in config.SERVICES.items():
        text = f"{service['emoji']} {service['name']} - {service['price']}₽"
        builder.button(text=text, callback_data=f"service_{service_id}")
    builder.button(text="🎁 Мои скидки", callback_data="my_discounts")
    builder.button(text="📅 Записаться", callback_data="book_now")
    builder.adjust(1)
    return builder.as_markup()

def booking_dates_keyboard():
    builder = InlineKeyboardBuilder()
    today = datetime.now().date()

    for i in range(1, 8):
        date_obj = today + timedelta(days=i)
        date_str = date_obj.strftime("%d.%m.%Y")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date_obj.weekday()]
        text = f"{date_str} ({weekday})"

        if date_obj.weekday() >= 5:
            text = f"🎉 {text}"

        builder.button(text=text, callback_data=f"date_{date_str}")

    builder.button(text="🔙 Назад к услугам", callback_data="back_to_services")
    builder.adjust(2)
    return builder.as_markup()

def booking_times_keyboard():
    builder = InlineKeyboardBuilder()

    for time_slot in config.TIME_SLOTS:
        builder.button(text=time_slot, callback_data=f"time_{time_slot}")

    builder.button(text="🔙 Выбрать другую дату", callback_data="back_to_dates")
    builder.adjust(3)
    return builder.as_markup()

def confirm_booking_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, всё верно!", callback_data="confirm_booking")
    builder.button(text="🎁 Применить скидку", callback_data="apply_discount")
    builder.button(text="❌ Отменить", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()

def contact_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📞 Позвонить", url=f"tel:{config.SALON_INFO['phone_formatted']}")
    builder.button(text="📍 Как добраться?", callback_data="get_location")
    builder.button(text="✏️ Написать в Telegram", callback_data="write_to_admin")
    builder.button(text="🔙 В главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def gallery_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💅 Маникюр", callback_data="gallery_manicure")
    builder.button(text="👣 Педикюр", callback_data="gallery_pedicure")
    builder.button(text="🌟 Комбо", callback_data="gallery_combo")
    builder.button(text="🎨 Случайная работа", callback_data="gallery_random")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

def share_contact_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Отправить мой номер", request_contact=True)
    builder.button(text="❌ Отмена")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои записи", callback_data="my_appointments")
    builder.button(text="🎁 Мои скидки", callback_data="my_discounts")
    builder.button(text="⭐ Мои отзывы", callback_data="my_reviews")
    builder.button(text="🔄 Перенести запись", callback_data="reschedule_appointment")
    builder.button(text="❌ Отменить запись", callback_data="cancel_my_appointment")
    builder.button(text="🎫 Пригласить друга", callback_data="invite_friend")
    builder.button(text="🔙 В главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

def admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📝 Новые заявки", callback_data="admin_pending")
    builder.button(text="📅 Все записи", callback_data="admin_all")
    builder.button(text="👥 Управление клиентами", callback_data="admin_users")
    builder.button(text="🖼️ Управление галереей", callback_data="admin_gallery")
    builder.button(text="⭐ Управление отзывами", callback_data="admin_reviews")
    builder.button(text="📢 Индивидуальная рассылка", callback_data="admin_broadcast")
    builder.button(text="🎁 Управление скидками", callback_data="admin_discounts")
    builder.adjust(2)
    return builder.as_markup()

def admin_appointment_actions(appointment_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"admin_approve_{appointment_id}")
    builder.button(text="❌ Отклонить", callback_data=f"admin_reject_{appointment_id}")
    builder.button(text="📞 Позвонить клиенту", callback_data=f"admin_call_{appointment_id}")
    builder.button(text="💬 Написать клиенту", callback_data=f"admin_message_{appointment_id}")
    builder.button(text="✏️ Комментарий", callback_data=f"admin_comment_{appointment_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def review_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Оставить отзыв", callback_data="leave_review")
    builder.button(text="📷 Отзыв с фото", callback_data="leave_review_with_photo")
    builder.button(text="📖 Читать все отзывы", callback_data="read_reviews")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def rating_keyboard():
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"rate_{i}")
    builder.button(text="❌ Отмена", callback_data="cancel_review")
    builder.adjust(3, 2)
    return builder.as_markup()

def discount_keyboard(available_discounts):
    builder = InlineKeyboardBuilder()
    for discount in available_discounts:
        builder.button(text=f"🎁 {discount['name']} ({discount['percent']}%)",
                      callback_data=f"use_discount_{discount['id']}")
    builder.button(text="🚫 Без скидки", callback_data="no_discount")
    builder.button(text="🔙 Назад", callback_data="back_to_confirmation")
    builder.adjust(1)
    return builder.as_markup()

def appointment_actions_keyboard(appointment_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Перенести", callback_data=f"reschedule_{appointment_id}")
    builder.button(text="❌ Отменить", callback_data=f"cancel_{appointment_id}")
    builder.button(text="🔙 Назад", callback_data="my_appointments")
    builder.adjust(2)
    return builder.as_markup()

def admin_broadcast_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Всем пользователям", callback_data="broadcast_all")
    builder.button(text="🎯 По фильтру", callback_data="broadcast_filtered")
    builder.button(text="👤 Конкретному клиенту", callback_data="broadcast_single")
    builder.button(text="🔙 Назад", callback_data="back_to_admin")
    builder.adjust(1)
    return builder.as_markup()

def generate_referral_code():
    """Генерация уникального реферального кода"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_discounts_for_user(user):
    """Получение доступных скидок для пользователя"""
    discounts = []

    # Скидка на первую запись
    if user.visits_count == 0:
        discounts.append({
            'id': 'first_visit',
            'name': 'Первая запись',
            'percent': config.LOYALTY_SYSTEM['first_visit_discount'],
            'type': 'first_visit'
        })

    # Скидки за количество визитов
    for milestone, discount in config.LOYALTY_SYSTEM['visit_milestones'].items():
        if user.visits_count >= milestone:
            discounts.append({
                'id': f'milestone_{milestone}',
                'name': f'За {milestone} визитов',
                'percent': discount,
                'type': 'milestone'
            })

    # Скидка на день рождения
    if user.birthday:
        today = datetime.now().date()
        bday = datetime.strptime(user.birthday, "%d.%m.%Y").date()
        bday_this_year = bday.replace(year=today.year)

        # Проверяем день рождения в течение месяца
        if abs((bday_this_year - today).days) <= 15:
            discounts.append({
                'id': 'birthday',
                'name': 'День рождения',
                'percent': config.LOYALTY_SYSTEM['birthday_discount'],
                'type': 'birthday'
            })

    return discounts
