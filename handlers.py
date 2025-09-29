from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from config import States
from database import Database
from keyboards import main_menu_keyboard, dates_keyboard, events_keyboard, confirmation_keyboard, \
    unregister_events_keyboard, admin_menu_keyboard
import re
from admin_config import ADMIN_IDS

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

    if not volunteer and data not in ['cancel', 'help', 'admin']:
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

        # Проверяем очередь
        waiting_count = len(db.get_waiting_list_for_event(event_id))

        await query.edit_message_text(
            f"📋 Информация о мероприятии:\n\n"
            f"📅 Дата: {event['date']}\n"
            f"🕒 Время: {event['start_time']} - {event['end_time']}\n"
            f"🎬 Название: {event['title']}\n"
            f"🔞 Возрастное ограничение: {event['age_limit']}\n"
            f"👥 Свободных мест: {available_slots}/{event['max_volunteers']}\n"
            f"📋 Людей в очереди: {waiting_count}\n\n"
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

        if "очередь" in message.lower() or "позиция" in message.lower():
            # Если добавлен в очередь, отправляем дополнительную информацию
            event = db.get_event_by_id(event_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📋 Вы добавлены в очередь на мероприятие!\n\n"
                     f"📅 Дата: {event['date']}\n"
                     f"🕒 Время: {event['start_time']} - {event['end_time']}\n"
                     f"🎬 Название: {event['title']}\n\n"
                     f"{message}\n\n"
                     f"Мы уведомим вас, если место освободится!"
            )
        elif success:
            # Успешная запись
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
            waiting_list = db.get_volunteer_waiting_list(volunteer['id'])

            if registrations or waiting_list:
                events_text = "📋 Ваши записи на мероприятия:\n\n"

                if registrations:
                    events_text += "✅ Подтвержденные записи:\n"
                    for i, reg in enumerate(registrations, 1):
                        events_text += f"{i}. 📅 {reg['date']} {reg['start_time']}\n   🎬 {reg['title']}\n\n"

                if waiting_list:
                    events_text += "⏳ В очереди:\n"
                    for i, wait in enumerate(waiting_list, len(registrations) + 1):
                        events_text += f"{i}. 📅 {wait['date']} {wait['start_time']}\n   🎬 {wait['title']}\n   📊 Позиция в очереди: {wait['position']}\n\n"

                await query.edit_message_text(events_text)
            else:
                await query.edit_message_text("📭 У вас пока нет записей на мероприятия.")

    elif data == 'unregister':
        volunteer = db.get_volunteer_by_telegram_id(user_id)
        if volunteer:
            registrations = db.get_volunteer_registrations(volunteer['id'])
            waiting_list = db.get_volunteer_waiting_list(volunteer['id'])

            if registrations or waiting_list:
                await query.edit_message_text(
                    "Выберите мероприятие, от которого хотите отписаться:",
                    reply_markup=unregister_events_keyboard(volunteer['id'])
                )
            else:
                await query.edit_message_text("📭 У вас нет активных записей на мероприятия.")


    elif data.startswith('unreg_'):

        volunteer = db.get_volunteer_by_telegram_id(user_id)

        if volunteer:

            parts = data.split('_')

            if len(parts) >= 3:

                unreg_type = parts[1]  # 'event' или 'wait'

                record_id = int(parts[2])

                if unreg_type == 'event':

                    # Отписка от основного мероприятия

                    event = db.get_event_by_id(record_id)

                    if event:

                        success, message, next_volunteer = db.unregister_volunteer_from_event(volunteer['id'],
                                                                                              record_id)

                        await query.edit_message_text(message)

                        if success and next_volunteer:

                            # Уведомляем следующего волонтера в очереди

                            try:

                                await context.bot.send_message(

                                    chat_id=next_volunteer['telegram_id'],

                                    text=f"🎉 Отличные новости! Место освободилось!\n\n"

                                         f"Вы были автоматически записаны на мероприятие:\n"

                                         f"📅 Дата: {event['date']}\n"

                                         f"🕒 Время: {event['start_time']} - {event['end_time']}\n"

                                         f"🎬 Название: {event['title']}\n\n"

                                         f"Не забудьте подойти за 15 минут до начала!"

                                )

                            except Exception as e:

                                print(f"Error notifying next volunteer: {e}")

                    else:

                        await query.edit_message_text("❌ Мероприятие не найдено.")


                elif unreg_type == 'wait':

                    # Удаление из очереди ожидания

                    # Находим запись в waiting_list по ID

                    waiting_list = db.get_volunteer_waiting_list(volunteer['id'])

                    target_wait = None

                    for wait in waiting_list:

                        if wait['id'] == record_id:
                            target_wait = wait

                            break

                    if target_wait:

                        success = db.remove_from_waiting_list(volunteer['id'], target_wait['id'])

                        if success:

                            # Обновляем позиции в очереди

                            db._update_waiting_list_positions(target_wait['id'])

                            await query.edit_message_text("✅ Вы успешно удалены из очереди ожидания.")

                        else:

                            await query.edit_message_text("❌ Ошибка при удалении из очереди.")

                    else:

                        await query.edit_message_text("❌ Запись в очереди не найдена.")

        else:

            await query.edit_message_text("❌ Волонтер не найден. Пройдите регистрацию через /start")


    elif data == 'admin':

        if user_id in ADMIN_IDS:

            await query.edit_message_text(

                "👑 Админ-панель\n\nВыберите действие:",

                reply_markup=admin_menu_keyboard()

            )

        else:

            await query.edit_message_text("❌ У вас нет прав доступа к этой функции.")

    elif data == 'admin_queues':

        if user_id in ADMIN_IDS:

            waiting_lists = db.get_admin_waiting_lists()

            if waiting_lists:

                admin_text = "📋 Очереди на мероприятия:\n\n"

                for item in waiting_lists:
                    admin_text += f"🎬 {item['title']}\n"

                    admin_text += f"📅 {item['date']} {item['start_time']}\n"

                    admin_text += f"👥 В очереди: {item['queue_count']} чел.\n"

                    admin_text += f"👤 Волонтеры в очереди:\n{item['volunteers_info']}\n"

                    admin_text += "\n" + "=" * 50 + "\n\n"

                if len(admin_text) > 4000:

                    parts = [admin_text[i:i + 4000] for i in range(0, len(admin_text), 4000)]

                    for part in parts:
                        await query.message.reply_text(part)

                    await query.edit_message_text("✅ Информация об очередях отправлена.")

                else:

                    await query.edit_message_text(admin_text)

            else:

                await query.edit_message_text("📭 На данный момент очередей нет.")

        else:

            await query.edit_message_text("❌ У вас нет прав доступа к этой функции.")


    elif data == 'admin_stats':

        if user_id in ADMIN_IDS:

            # Добавьте здесь логику для статистики

            events = db.get_all_events()

            total_volunteers = 0

            total_waiting = 0

            for event in events:
                registrations_count = db.get_registrations_count(event['id'])

                waiting_count = len(db.get_waiting_list_for_event(event['id']))

                total_volunteers += registrations_count

                total_waiting += waiting_count

            stats_text = (

                f"📊 Статистика мероприятий:\n\n"

                f"📅 Всего мероприятий: {len(events)}\n"

                f"👥 Всего записано волонтеров: {total_volunteers}\n"

                f"⏳ Всего в очередях: {total_waiting}\n"

                f"📈 Заполняемость: {round((total_volunteers / (len(events) * 6)) * 100, 1)}%"

            )

            await query.edit_message_text(stats_text, reply_markup=admin_menu_keyboard())

    elif data == 'help':
        await query.edit_message_text(
            "🤖 Команды бота:\n\n"
            "/start - Начать регистрацию/работать с ботом\n"
            "/help - Показать эту справку\n\n"
            "После регистрации вы сможете:\n"
            "• 📝 Записываться на мероприятия\n"
            "• 📋 Просматривать свои записи\n"
            "• ❌ Отписываться от мероприятий\n\n"
            "📊 Если мероприятие заполнено, вы будете добавлены в очередь!"
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
        "• ❌ Отписываться от мероприятий\n\n"
        "📊 Если мероприятие заполнено, вы будете добавлены в очередь!"
    )