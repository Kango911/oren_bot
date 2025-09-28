from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from config import States
from database import Database
from keyboards import main_menu_keyboard, dates_keyboard, events_keyboard, confirmation_keyboard, \
    unregister_events_keyboard
import re

db = Database()


async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    telegram_id = user.id
    context.user_data['telegram_id'] = telegram_id

    # Проверяем, зарегистрирован ли уже волонтер
    volunteer = db.get_volunteer_by_telegram_id(telegram_id)

    if volunteer:
        # Волонтер уже зарегистрирован
        await update.message.reply_text(
            f"С возвращением, {volunteer['full_name']}! 👋\n"
            "Выберите действие:",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    else:
        # Новый волонтер - начинаем регистрацию
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n"
            "Я бот для записи волонтеров на мероприятия кинофестиваля.\n\n"
            "Для начала работы нам нужно собрать базовую информацию.\n"
            "Пожалуйста, введите ваш номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX:"
        )
        return States.PHONE


async def get_phone(update: Update, context: CallbackContext) -> int:
    phone = update.message.text.strip()

    # Проверяем формат номера телефона
    if not re.match(r'^(\+7|8)\d{10}$', phone):
        await update.message.reply_text(
            "❌ Неверный формат номера телефона.\n"
            "Пожалуйста, введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX:"
        )
        return States.PHONE

    context.user_data['phone'] = phone
    await update.message.reply_text("✅ Отлично! Теперь введите ваше ФИО (полностью):")
    return States.FIO


async def get_fio(update: Update, context: CallbackContext) -> int:
    fio = update.message.text.strip()

    if len(fio) < 5:  # Минимальная проверка на валидность ФИО
        await update.message.reply_text("❌ ФИО слишком короткое. Пожалуйста, введите полное ФИО:")
        return States.FIO

    context.user_data['fio'] = fio

    # Сохраняем волонтера в базу данных
    telegram_id = context.user_data['telegram_id']
    phone = context.user_data['phone']

    volunteer_id = db.add_volunteer(telegram_id, phone, fio)

    if volunteer_id:
        await update.message.reply_text(
            f"✅ Регистрация завершена, {fio}!\n\n"
            "Теперь вы можете записываться на мероприятия кинофестиваля.",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при регистрации. Пожалуйста, попробуйте снова командой /start"
        )

    return ConversationHandler.END


async def cancel_registration(update: Update, context: CallbackContext) -> int:
    if update.message:
        await update.message.reply_text(
            "Регистрация отменена. Если хотите начать заново, используйте /start"
        )
    elif update.callback_query:
        query = update.callback_query
        await query.edit_message_text(
            "Регистрация отменена. Если хотите начать заново, используйте /start"
        )
    return ConversationHandler.END


async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()  # Ответ на callback query чтобы убрать "часики" в интерфейсе
    data = query.data
    user_id = context.user_data.get('telegram_id', query.from_user.id)

    # Обновляем telegram_id в context.user_data
    if 'telegram_id' not in context.user_data:
        context.user_data['telegram_id'] = user_id

    # Проверяем, зарегистрирован ли волонтер
    volunteer = db.get_volunteer_by_telegram_id(user_id)

    if not volunteer and data not in ['cancel', 'help']:
        await query.edit_message_text(
            "❌ Вы не зарегистрированы как волонтер.\n"
            "Пожалуйста, завершите регистрацию, введя команду /start"
        )
        return

    if data == 'register':
        await query.edit_message_text(
            "Выберите день мероприятия:",
            reply_markup=dates_keyboard()
        )

    elif data.startswith('date_'):
        date = data.split('_')[1]
        context.user_data['selected_date'] = date

        events = db.get_events_by_date(date)
        if not events:
            await query.edit_message_text(
                f"На {date} мероприятий не найдено.",
                reply_markup=dates_keyboard()
            )
            return

        await query.edit_message_text(
            f"Выберите мероприятие на {date}:",
            reply_markup=events_keyboard(date)
        )

    elif data.startswith('event_'):
        event_id = int(data.split('_')[1])
        context.user_data['selected_event_id'] = event_id

        event = db.get_event_by_id(event_id)
        if not event:
            await query.edit_message_text("❌ Мероприятие не найдено.")
            return

        current_count = db.get_registrations_count(event_id)
        available_slots = event['max_volunteers'] - current_count

        await query.edit_message_text(
            f"📋 Информация о мероприятии:\n\n"
            f"📅 Дата: {event['date']}\n"
            f"🕒 Время: {event['start_time']} - {event['end_time']}\n"
            f"🎬 Название: {event['title']}\n"
            f"🔞 Возрастное ограничение: {event['age_limit']}\n"
            f"👥 Свободных мест: {available_slots}/{event['max_volunteers']}\n\n"
            f"Подтвердите запись на это мероприятие:",
            reply_markup=confirmation_keyboard()
        )

    elif data == 'confirm':
        event_id = context.user_data.get('selected_event_id')
        if not event_id:
            await query.edit_message_text("❌ Ошибка: мероприятие не выбрано.")
            return

        volunteer = db.get_volunteer_by_telegram_id(user_id)
        if not volunteer:
            await query.edit_message_text("❌ Волонтер не найден. Пройдите регистрацию через /start")
            return

        success, message = db.register_volunteer_for_event(volunteer['id'], event_id)
        await query.edit_message_text(message)

        if success:
            # Отправляем подтверждение в личные сообщения
            event = db.get_event_by_id(event_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Вы успешно записаны на мероприятие!\n\n"
                     f"📅 Дата: {event['date']}\n"
                     f"🕒 Время: {event['start_time']} - {event['end_time']}\n"
                     f"🎬 Название: {event['title']}\n\n"
                     f"Не забудьте подойти за 15 минут до начала!"
            )

    elif data == 'my_events':
        volunteer = db.get_volunteer_by_telegram_id(user_id)
        if volunteer:
            registrations = db.get_volunteer_registrations(volunteer['id'])
            if registrations:
                events_text = "📋 Ваши записи на мероприятия:\n\n"
                for i, reg in enumerate(registrations, 1):
                    events_text += f"{i}. 📅 {reg['date']} {reg['start_time']}\n   🎬 {reg['title']}\n\n"
                await query.edit_message_text(events_text)
            else:
                await query.edit_message_text("📭 У вас пока нет записей на мероприятия.")

    elif data == 'unregister':
        volunteer = db.get_volunteer_by_telegram_id(user_id)
        if volunteer:
            registrations = db.get_volunteer_registrations(volunteer['id'])
            if registrations:
                await query.edit_message_text(
                    "Выберите мероприятие, от которого хотите отписаться:",
                    reply_markup=unregister_events_keyboard(volunteer['id'])
                )
            else:
                await query.edit_message_text("📭 У вас нет активных записей на мероприятия.")

    elif data.startswith('unreg_'):
        event_id = int(data.split('_')[1])
        volunteer = db.get_volunteer_by_telegram_id(user_id)

        if volunteer:
            success, message = db.unregister_volunteer_from_event(volunteer['id'], event_id)
            await query.edit_message_text(message)

            if success:
                event = db.get_event_by_id(event_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Вы отписаны от мероприятия:\n\n"
                         f"📅 {event['date']} {event['start_time']}\n"
                         f"🎬 {event['title']}"
                )

    elif data == 'help':
        await query.edit_message_text(
            "🤖 Команды бота:\n\n"
            "/start - Начать регистрацию/работать с ботом\n"
            "/help - Показать эту справку\n\n"
            "После регистрации вы сможете:\n"
            "• 📝 Записываться на мероприятия\n"
            "• 📋 Просматривать свои записи\n"
            "• ❌ Отписываться от мероприятий"
        )

    elif data in ['back_to_main', 'cancel']:
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=main_menu_keyboard()
        )

    elif data == 'back_to_dates':
        await query.edit_message_text(
            "Выберите день мероприятия:",
            reply_markup=dates_keyboard()
        )

    # Обработка нажатия на кнопку отмены в процессе регистрации
    elif data == 'cancel_registration':
        await query.edit_message_text(
            "Регистрация отменена. Если хотите начать заново, используйте /start"
        )
        return ConversationHandler.END


async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🤖 Команды бота:\n\n"
        "/start - Начать регистрацию/работать с ботом\n"
        "/help - Показать эту справку\n\n"
        "После регистрации вы сможете:\n"
        "• 📝 Записываться на мероприятия\n"
        "• 📋 Просматривать свои записи\n"
        "• ❌ Отписываться от мероприятий"
    )