from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import Database

db = Database()


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Записаться на мероприятие", callback_data='register')],
        [InlineKeyboardButton("📋 Мои записи", callback_data='my_events')],
        [InlineKeyboardButton("❌ Отписаться от мероприятия", callback_data='unregister')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')]
    ]
    return InlineKeyboardMarkup(keyboard)


def dates_keyboard():
    # Получаем уникальные даты из базы данных
    events = db.get_all_events()
    dates = set()
    for event in events:
        dates.add(event['date'])

    dates = sorted(list(dates))
    keyboard = []
    for date in dates:
        # Форматируем дату для отображения
        formatted_date = date.strftime("%d.%m.%Y") if hasattr(date, 'strftime') else date
        keyboard.append([InlineKeyboardButton(f"📅 {formatted_date}", callback_data=f'date_{date}')])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
    return InlineKeyboardMarkup(keyboard)


def events_keyboard(date):
    events = db.get_events_by_date(date)
    keyboard = []
    for event in events:
        # Проверяем количество записанных волонтеров
        current_count = db.get_registrations_count(event['id'])
        available_slots = event['max_volunteers'] - current_count

        # Сокращаем длинное название
        title_short = event['title'][:30] + "..." if len(event['title']) > 30 else event['title']

        button_text = f"🕒 {event['start_time']} - {title_short} ({available_slots}/{event['max_volunteers']} мест)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'event_{event["id"]}')])

    keyboard.append([InlineKeyboardButton("🔙 Назад к выбору даты", callback_data='back_to_dates')])
    return InlineKeyboardMarkup(keyboard)


def confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить запись", callback_data='confirm')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel')]
    ]
    return InlineKeyboardMarkup(keyboard)


def unregister_events_keyboard(volunteer_id):
    registrations = db.get_volunteer_registrations(volunteer_id)
    keyboard = []
    for reg in registrations:
        # Сокращаем длинное название
        title_short = reg['title'][:30] + "..." if len(reg['title']) > 30 else reg['title']
        button_text = f"📅 {reg['date']} {reg['start_time']} - {title_short}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'unreg_{reg["id"]}')])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
    return InlineKeyboardMarkup(keyboard)


def registration_cancel_keyboard():
    keyboard = [
        [InlineKeyboardButton("❌ Отменить регистрацию", callback_data='cancel_registration')]
    ]
    return InlineKeyboardMarkup(keyboard)