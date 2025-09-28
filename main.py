from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
from config import BOT_TOKEN, States
from handlers import start, button_click, get_phone, get_fio, cancel_registration, help_command
from database import Database
from events_data import EVENTS_DATA
import logging
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main():
    # Инициализация базы данных и заполнение мероприятий (только если их нет)
    db = Database()
    db.populate_events(EVENTS_DATA)

    # Создание application
    application = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler для регистрации (должен быть добавлен ПЕРВЫМ)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            States.PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
            States.FIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_registration)
        ]
    )

    # Добавляем обработчики в правильном порядке
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(CommandHandler('help', help_command))

    async def handle_text(update, context):
        await update.message.reply_text(
            "Используйте команды:\n/start - начать работу\n/help - помощь"
        )

    # Обработчик для любых текстовых сообщений (добавляем ПОСЛЕДНИМ)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запуск бота с использованием разных методов в зависимости от окружения
    print("Бот запущен...")

    # Для сред, где уже есть running event loop (например, Jupyter, некоторые IDE)
    try:
        application.run_polling()
    except RuntimeError as e:
        if "event loop" in str(e):
            # Создаем новую event loop для сред, где это необходимо
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            application.run_polling()
        else:
            raise e


if __name__ == '__main__':
    main()