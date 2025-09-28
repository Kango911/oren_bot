from TOKEN import TOKEN

# Настройки бота
BOT_TOKEN = TOKEN

# Настройки базы данных
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'rootroot',
    'database': 'volunteer_bot'
}

# Состояния для FSM
class States:
    PHONE = 1
    FIO = 2