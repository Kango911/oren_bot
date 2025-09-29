import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG


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

        # Таблица очереди на мероприятия
        waiting_list_table = """
        CREATE TABLE IF NOT EXISTS waiting_list (
            id INT AUTO_INCREMENT PRIMARY KEY,
            volunteer_id INT NOT NULL,
            event_id INT NOT NULL,
            position INT NOT NULL,
            join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
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
            cursor.execute(waiting_list_table)
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

    def get_waiting_list_position(self, event_id, volunteer_id):
        """Получить позицию в очереди для волонтера"""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT position 
                FROM waiting_list 
                WHERE event_id = %s AND volunteer_id = %s
            """, (event_id, volunteer_id))
            result = cursor.fetchone()
            return result[0] if result else None
        except Error as e:
            print(f"Error getting waiting list position: {e}")
            return None

    def add_to_waiting_list(self, volunteer_id, event_id):
        """Добавить волонтера в очередь на мероприятие"""
        cursor = self.connection.cursor()
        try:
            # Получаем текущую максимальную позицию в очереди
            cursor.execute("SELECT COALESCE(MAX(position), 0) FROM waiting_list WHERE event_id = %s", (event_id,))
            max_position = cursor.fetchone()[0]
            new_position = max_position + 1

            cursor.execute("""
                INSERT INTO waiting_list (volunteer_id, event_id, position) 
                VALUES (%s, %s, %s)
            """, (volunteer_id, event_id, new_position))
            self.connection.commit()
            return True, new_position
        except Error as e:
            print(f"Error adding to waiting list: {e}")
            return False, 0

    def remove_from_waiting_list(self, volunteer_id, waiting_list_id):
        """Удалить волонтера из очереди по ID записи waiting_list"""
        cursor = self.connection.cursor()
        try:
            # Сначала получаем event_id для обновления позиций
            cursor.execute("SELECT event_id FROM waiting_list WHERE id = %s", (waiting_list_id,))
            result = cursor.fetchone()
            if not result:
                return False

            event_id = result[0]

            # Удаляем запись
            cursor.execute("DELETE FROM waiting_list WHERE id = %s AND volunteer_id = %s",
                           (waiting_list_id, volunteer_id))
            deleted = cursor.rowcount > 0

            if deleted:
                # Обновляем позиции в очереди
                self._update_waiting_list_positions(event_id)

            self.connection.commit()
            return deleted
        except Error as e:
            print(f"Error removing from waiting list: {e}")
            return False

    def get_waiting_list_for_event(self, event_id):
        """Получить список волонтеров в очереди на мероприятие"""
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT wl.*, v.full_name, v.phone, v.telegram_id
                FROM waiting_list wl
                JOIN volunteers v ON wl.volunteer_id = v.id
                WHERE wl.event_id = %s
                ORDER BY wl.position
            """, (event_id,))
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting waiting list: {e}")
            return []

    def is_in_waiting_list(self, volunteer_id, event_id):
        """Проверить, находится ли волонтер в очереди на мероприятие"""
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT id FROM waiting_list WHERE volunteer_id = %s AND event_id = %s",
                           (volunteer_id, event_id))
            return cursor.fetchone() is not None
        except Error as e:
            print(f"Error checking waiting list: {e}")
            return False

    def register_volunteer_for_event(self, volunteer_id, event_id):
        # Проверяем лимит
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Мероприятие не найдено"

        current_count = self.get_registrations_count(event_id)

        if current_count >= event['max_volunteers']:
            # Проверяем, не находится ли уже волонтер в очереди
            if self.is_in_waiting_list(volunteer_id, event_id):
                position = self.get_waiting_list_position(event_id, volunteer_id)
                return False, f"Вы уже находитесь в очереди на это мероприятие. Ваша позиция: {position}"

            # Добавляем в очередь
            success, position = self.add_to_waiting_list(volunteer_id, event_id)
            if success:
                return False, f"На это мероприятие уже набрано максимальное количество волонтеров. Вы добавлены в очередь. Ваша позиция: {position}"
            else:
                return False, "Ошибка при добавлении в очередь."

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
            # Удаляем из основной записи
            cursor.execute("DELETE FROM registrations WHERE volunteer_id = %s AND event_id = %s",
                           (volunteer_id, event_id))

            deleted_count = cursor.rowcount

            if deleted_count > 0:
                # Если была удалена запись, проверяем очередь
                waiting_list = self.get_waiting_list_for_event(event_id)
                if waiting_list:
                    # Берем первого из очереди и добавляем в основную запись
                    next_volunteer = waiting_list[0]
                    cursor.execute("INSERT INTO registrations (volunteer_id, event_id) VALUES (%s, %s)",
                                   (next_volunteer['volunteer_id'], event_id))
                    # Удаляем из очереди
                    cursor.execute("DELETE FROM waiting_list WHERE volunteer_id = %s AND event_id = %s",
                                   (next_volunteer['volunteer_id'], event_id))

                    # Обновляем позиции в очереди
                    self._update_waiting_list_positions(event_id)

                    self.connection.commit()

                    # Возвращаем информацию о следующем волонтере для уведомления
                    return True, "Вы успешно выписаны с мероприятия.", next_volunteer

                self.connection.commit()
                return True, "Вы успешно выписаны с мероприятия.", None
            else:
                # Проверяем, может быть волонтер в очереди
                if self.is_in_waiting_list(volunteer_id, event_id):
                    self.remove_from_waiting_list(volunteer_id, event_id)
                    self._update_waiting_list_positions(event_id)
                    return True, "Вы удалены из очереди на мероприятие.", None
                else:
                    return False, "Вы не были записаны на это мероприятие.", None
        except Error as e:
            print(f"Error unregistering volunteer: {e}")
            return False, "Ошибка при отписке от мероприятия.", None

    def _update_waiting_list_positions(self, event_id):
        """Обновить позиции в очереди после изменений"""
        cursor = self.connection.cursor()
        try:
            # Получаем список ID в правильном порядке
            cursor.execute("SELECT id FROM waiting_list WHERE event_id = %s ORDER BY join_date", (event_id,))
            rows = cursor.fetchall()

            # Обновляем позиции
            for new_position, (row_id,) in enumerate(rows, 1):
                cursor.execute("UPDATE waiting_list SET position = %s WHERE id = %s", (new_position, row_id))

            self.connection.commit()
        except Error as e:
            print(f"Error updating waiting list positions: {e}")

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

    def get_volunteer_waiting_list(self, volunteer_id):
        """Получить мероприятия, на которые волонтер стоит в очереди"""
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT e.*, wl.position
                FROM events e
                JOIN waiting_list wl ON e.id = wl.event_id
                WHERE wl.volunteer_id = %s
                ORDER BY e.date, e.start_time
            """, (volunteer_id,))
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting waiting list: {e}")
            return []

    def populate_events(self, events_list):
        """Заполнение мероприятий без изменения существующих записей"""
        cursor = self.connection.cursor()
        try:
            # Проверяем, есть ли уже мероприятия
            cursor.execute("SELECT COUNT(*) FROM events")
            event_count = cursor.fetchone()[0]

            if event_count == 0:
                # Если мероприятий нет, заполняем
                for event in events_list:
                    cursor.execute("""
                        INSERT INTO events (date, start_time, end_time, title, age_limit, max_volunteers)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (event['date'], event['start_time'], event['end_time'],
                          event['title'], event['age_limit'], event['max_volunteers']))
                self.connection.commit()
                print("Events populated successfully")
            else:
                print("Events already exist in database, skipping population")
        except Error as e:
            print(f"Error populating events: {e}")

    def get_all_events(self):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM events ORDER BY date, start_time")
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting all events: {e}")
            return []

    def get_admin_waiting_lists(self):
        """Получить информацию об очередях для админа"""
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT e.id as event_id, e.title, e.date, e.start_time, 
                       COUNT(wl.id) as queue_count
                FROM events e
                LEFT JOIN waiting_list wl ON e.id = wl.event_id
                GROUP BY e.id, e.title, e.date, e.start_time
                HAVING queue_count > 0
                ORDER BY e.date, e.start_time
            """)
            events_with_queues = cursor.fetchall()

            # Для каждого мероприятия получаем детальную информацию о волонтерах в очереди
            for event in events_with_queues:
                waiting_list = self.get_waiting_list_for_event(event['event_id'])
                volunteers_info = []
                for volunteer in waiting_list:
                    volunteers_info.append(
                        f"{volunteer['full_name']} (тел.: {volunteer['phone']}, TG ID: {volunteer['telegram_id']}, позиция: {volunteer['position']})")
                event['volunteers_info'] = "\n".join(volunteers_info) if volunteers_info else "Нет волонтеров в очереди"

            return events_with_queues
        except Error as e:
            print(f"Error getting admin waiting lists: {e}")
            return []

    def get_waiting_list_by_id(self, waiting_list_id):
        """Получить запись из waiting_list по ID"""
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT wl.*, e.title, e.date, e.start_time, e.end_time
                FROM waiting_list wl
                JOIN events e ON wl.event_id = e.id
                WHERE wl.id = %s
            """, (waiting_list_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting waiting list by ID: {e}")
            return None