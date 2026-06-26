import os

import psycopg2
from clickhouse_driver import Client
from pymongo import MongoClient

# ============================================================================
# 1. ПОДКЛЮЧЕНИЕ И РАБОТА С POSTGRESQL
# ============================================================================
print("=== Шаг 1: Проверка PostgreSQL ===")
pg_conn = psycopg2.connect(
    host="localhost", port=5432, user="user", password="password", dbname="example_db"
)
pg_cursor = pg_conn.cursor()

pg_cursor.execute(
    "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name TEXT);"
)
pg_cursor.execute("INSERT INTO users(name) VALUES (%s)", ("Alice",))
pg_cursor.execute("SELECT * FROM users;")

print("PostgreSQL данные:", pg_cursor.fetchall())
pg_conn.commit()
pg_cursor.close()
pg_conn.close()


# ============================================================================
# 2. АВТОМАТИЧЕСКАЯ ПОДГОТОВКА SQL-ФАЙЛА ДЛЯ STEPIK
# ============================================================================
print("\n=== Шаг 2: Подготовка SQL-скрипта для ClickHouse ===")

sql_dir = "sql"
sql_file_path = os.path.join(sql_dir, "clickhouse_solution.sql")

# Сами SQL-команды, которые требуют на Stepik (создание таблиц и MV)
clickhouse_ddl_content = """-- 1. СЫРАЯ ТАБЛИЦА ЛОГОВ (Храним 30 дней)
CREATE TABLE IF NOT EXISTS user_events (
    user_id UInt64,
    event_type String,
    points_spent UInt32,
    event_time DateTime
) ENGINE = MergeTree() 
ORDER BY (event_time, user_id) 
TTL event_time + INTERVAL 30 DAY;

-- 2. АГРЕГИРОВАННАЯ ТАБЛИЦА (Храним 180 дней)
CREATE TABLE IF NOT EXISTS user_events_daily_agg (
    event_date Date,
    event_type String,
    unique_users AggregateFunction(uniq, UInt64),
    total_points AggregateFunction(sum, UInt32),
    actions_count AggregateFunction(count)
) ENGINE = AggregatingMergeTree() 
ORDER BY (event_date, event_type) 
TTL event_date + INTERVAL 180 DAY;

-- 3. MATERIALIZED VIEW ДЛЯ АВТОАГРЕГАЦИИ
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_events_daily_agg 
TO user_events_daily_agg AS
SELECT
    toDate(event_time) AS event_date,
    event_type,
    uniqState(user_id) AS unique_users,
    sumState(points_spent) AS total_points,
    countState() AS actions_count
FROM user_events
GROUP BY event_date, event_type;
"""

# Создаем папку sql/, если её нет, и записываем туда файл
os.makedirs(sql_dir, exist_ok=True)
with open(sql_file_path, "w", encoding="utf-8") as f:
    f.write(clickhouse_ddl_content)
print(
    f"Файл успешно сохранен по пути: {sql_file_path} (Его содержимое копируй на Stepik!)"
)


# ============================================================================
# 3. ПОДКЛЮЧЕНИЕ И ВЫПОЛНЕНИЕ ЗАДАНИЯ В CLICKHOUSE
# ============================================================================
print("\n=== Шаг 3: Выполнение задания в ClickHouse ===")
ch_client = Client(
    host="localhost",
    user="user",
    password="strongpassword",
    port=9000,  # TCP порт
)

# Накатываем структуру из созданного файла
print("Применяем структуру таблиц и MV...")
with open(sql_file_path, "r", encoding="utf-8") as f:
    # Разделяем по точке с запятой, игнорируя комментарии и пустые строки
    queries = [q.strip() for q in f.read().split(";") if q.strip()]
    for query in queries:
        ch_client.execute(query)

# Очищаем таблицу перед вставкой тестовых данных (чтобы избежать дублирования при перезапусках скрипта)
ch_client.execute("TRUNCATE TABLE user_events")

# Вставка тестовых данных из задания
print("Загружаем тестовые логи...")
insert_query = """
INSERT INTO user_events VALUES
(1, 'login', 0, now() - INTERVAL 10 DAY), (2, 'signup', 0, now() - INTERVAL 10 DAY), (3, 'login', 0, now() - INTERVAL 10 DAY),
(1, 'login', 0, now() - INTERVAL 7 DAY), (2, 'login', 0, now() - INTERVAL 7 DAY), (3, 'purchase', 30, now() - INTERVAL 7 DAY),
(1, 'purchase', 50, now() - INTERVAL 5 DAY), (2, 'logout', 0, now() - INTERVAL 5 DAY), (4, 'login', 0, now() - INTERVAL 5 DAY),
(1, 'login', 0, now() - INTERVAL 3 DAY), (3, 'purchase', 70, now() - INTERVAL 3 DAY), (5, 'signup', 0, now() - INTERVAL 3 DAY),
(2, 'purchase', 20, now() - INTERVAL 1 DAY), (4, 'logout', 0, now() - INTERVAL 1 DAY), (5, 'login', 0, now() - INTERVAL 1 DAY),
(1, 'purchase', 25, now()), (2, 'login', 0, now()), (3, 'logout', 0, now()), (6, 'signup', 0, now()), (6, 'purchase', 100, now())
"""
ch_client.execute(insert_query)

# 1. Запрос быстрой аналитики (Критерий: использование *Merge функций)
print("\n--- Результат быстрой аналитики по дням (через Merge) ---")
analytics_query = """
SELECT 
    event_date, 
    event_type, 
    uniqMerge(unique_users) AS users, 
    sumMerge(total_points) AS points, 
    countMerge(actions_count) AS actions
FROM user_events_daily_agg 
GROUP BY event_date, event_type 
ORDER BY event_date, event_type
"""
for row in ch_client.execute(analytics_query):
    print(
        f"Дата: {row[0]} | Событие: {row[1]:<8} | Уникальных юзеров: {row[2]} | Потрачено баллов: {row[3]:<3} | Действий: {row[4]}"
    )

# 2. Запрос расчета Retention 7 дней
print("\n--- Расчет Retention за 7 дней ---")
retention_query = """
WITH user_cohorts AS (
    SELECT 
        user_id, 
        toDate(event_time) AS event_date, 
        min(toDate(event_time)) OVER (PARTITION BY user_id) AS first_date
    FROM user_events
)
SELECT 
    uniqExact(user_id) AS total_users_day_0,
    uniqExactIf(user_id, event_date > first_date AND event_date <= first_date + 7) AS returned_in_7_days,
    round((returned_in_7_days / total_users_day_0) * 100, 2) AS retention_7d_percent
FROM user_cohorts
"""
retention_result = ch_client.execute(retention_query)
if retention_result:
    total, returned, pct = retention_result[0]
    print("Формат: total_users_day_0 | returned_in_7_days | retention_7d_percent |")
    print(f"Итог:   {total} | {returned} | {pct}% |")


# ============================================================================
# 4. ПОДКЛЮЧЕНИЕ И РАБОТА С MONGODB
# ============================================================================
print("\n=== Шаг 4: Проверка MongoDB ===")
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["test_db"]
mongo_collection = mongo_db["users"]

mongo_collection.insert_one({"name": "Charlie"})
print("MongoDB данные:", list(mongo_collection.find({}, {"_id": 0})))

print("\n[Успешно] Все базы данных проверены, задание для ClickHouse выполнено!")
