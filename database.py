import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG
from datetime import datetime

class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        self.create_tables()

    def connect(self):
        try:
            self.connection = mysql.connector.connect(**DB_CONFIG)
            if self.connection.is_connected():
                print("Connected to MySQL database")
        except Error as e:
            print(f"Error: {e}")

    def create_tables(self):
        # Таблица волонтеров
        volunteers_table = """
        CREATE TABLE IF NOT EXISTS volunteers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            phone VARCHAR(20) NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Таблица мероприятий
        events_table = """
        CREATE TABLE IF NOT EXISTS events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            title VARCHAR(255) NOT NULL,
            age_limit VARCHAR(10) NOT NULL,
            max_volunteers INT NOT NULL,
            current_volunteers INT DEFAULT 0
        );
        """

        # Таблица записей волонтеров на мероприятия
        registrations_table = """
        CREATE TABLE IF NOT EXISTS registrations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            volunteer_id INT NOT NULL,
            event_id INT NOT NULL,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (volunteer_id) REFERENCES volunteers(id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            UNIQUE(volunteer_id, event_id)
        );
        """

        cursor = self.connection.cursor()
        try:
            cursor.execute(volunteers_table)
            cursor.execute(events_table)
            cursor.execute(registrations_table)
            self.connection.commit()
            print("Tables created successfully")
        except Error as e:
            print(f"Error creating tables: {e}")
        finally:
            cursor.close()

    def add_volunteer(self, telegram_id, phone, full_name):
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO volunteers (telegram_id, phone, full_name) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE phone=%s, full_name=%s
            """, (telegram_id, phone, full_name, phone, full_name))
            self.connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Error adding volunteer: {e}")
            return None

    def get_volunteer_by_telegram_id(self, telegram_id):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM volunteers WHERE telegram_id = %s", (telegram_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting volunteer: {e}")
            return None

    def get_events_by_date(self, date):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM events WHERE date = %s ORDER BY start_time", (date,))
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting events: {e}")
            return []

    def get_event_by_id(self, event_id):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting event: {e}")
            return None

    def get_registrations_count(self, event_id):
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM registrations WHERE event_id = %s", (event_id,))
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error counting registrations: {e}")
            return 0

    def register_volunteer_for_event(self, volunteer_id, event_id):
        # Проверяем лимит
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Мероприятие не найдено"

        current_count = self.get_registrations_count(event_id)
        if current_count >= event['max_volunteers']:
            return False, "На это мероприятие уже набрано максимальное количество волонтеров."

        cursor = self.connection.cursor()
        try:
            cursor.execute("INSERT INTO registrations (volunteer_id, event_id) VALUES (%s, %s)",
                         (volunteer_id, event_id))
            self.connection.commit()
            return True, "Успешная запись на мероприятие."
        except Error as e:
            print(f"Error registering volunteer: {e}")
            return False, "Ошибка при записи на мероприятие."

    def unregister_volunteer_from_event(self, volunteer_id, event_id):
        cursor = self.connection.cursor()
        try:
            cursor.execute("DELETE FROM registrations WHERE volunteer_id = %s AND event_id = %s",
                         (volunteer_id, event_id))
            self.connection.commit()
            if cursor.rowcount > 0:
                return True, "Вы успешно выписаны с мероприятия."
            else:
                return False, "Вы не были записаны на это мероприятие."
        except Error as e:
            print(f"Error unregistering volunteer: {e}")
            return False, "Ошибка при отписке от мероприятия."

    def get_volunteer_registrations(self, volunteer_id):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT e.*, r.registration_date 
                FROM events e
                JOIN registrations r ON e.id = r.event_id
                WHERE r.volunteer_id = %s
                ORDER BY e.date, e.start_time
            """, (volunteer_id,))
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting registrations: {e}")
            return []

    def populate_events(self, events_list):
        cursor = self.connection.cursor()
        try:
            cursor.execute("DELETE FROM events")  # Очищаем таблицу перед заполнением
            for event in events_list:
                cursor.execute("""
                    INSERT INTO events (date, start_time, end_time, title, age_limit, max_volunteers)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (event['date'], event['start_time'], event['end_time'],
                      event['title'], event['age_limit'], event['max_volunteers']))
            self.connection.commit()
            print("Events populated successfully")
        except Error as e:
            print(f"Error populating events: {e}")

    # Добавляем недостающий метод
    def get_all_events(self):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM events ORDER BY date, start_time")
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting all events: {e}")
            return []