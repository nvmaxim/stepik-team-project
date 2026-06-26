-- ============================================================================
-- 1. СЫРАЯ ТАБЛИЦА ЛОГОВ (Храним 30 дней)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_events (
    user_id UInt64,
    event_type String,
    points_spent UInt32,
    event_time DateTime
) ENGINE = MergeTree() 
ORDER BY (event_time, user_id) 
TTL event_time + INTERVAL 30 DAY;

-- ============================================================================
-- 2. АГРЕГИРОВАННАЯ ТАБЛИЦА (Храним 180 дней)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_events_daily_agg (
    event_date Date,
    event_type String,
    unique_users AggregateFunction(uniq, UInt64),
    total_points AggregateFunction(sum, UInt32),
    actions_count AggregateFunction(count)
) ENGINE = AggregatingMergeTree() 
ORDER BY (event_date, event_type) 
TTL event_date + INTERVAL 180 DAY;

-- ============================================================================
-- 3. MATERIALIZED VIEW ДЛЯ АВТОАГРЕГАЦИИ
-- ============================================================================
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

-- ============================================================================
-- 4. ЗАПРОС ДЛЯ ВСТАВКИ ТЕСТОВЫХ ДАННЫХ
-- ============================================================================
INSERT INTO user_events VALUES
-- События 10 дней назад
(1, 'login', 0, now() - INTERVAL 10 DAY),
(2, 'signup', 0, now() - INTERVAL 10 DAY),
(3, 'login', 0, now() - INTERVAL 10 DAY),
-- События 7 дней назад
(1, 'login', 0, now() - INTERVAL 7 DAY),
(2, 'login', 0, now() - INTERVAL 7 DAY),
(3, 'purchase', 30, now() - INTERVAL 7 DAY),
-- События 5 дней назад
(1, 'purchase', 50, now() - INTERVAL 5 DAY),
(2, 'logout', 0, now() - INTERVAL 5 DAY),
(4, 'login', 0, now() - INTERVAL 5 DAY),
-- События 3 дня назад
(1, 'login', 0, now() - INTERVAL 3 DAY),
(3, 'purchase', 70, now() - INTERVAL 3 DAY),
(5, 'signup', 0, now() - INTERVAL 3 DAY),
-- События вчера
(2, 'purchase', 20, now() - INTERVAL 1 DAY),
(4, 'logout', 0, now() - INTERVAL 1 DAY),
(5, 'login', 0, now() - INTERVAL 1 DAY),
-- События сегодня
(1, 'purchase', 25, now()),
(2, 'login', 0, now()),
(3, 'logout', 0, now()),
(6, 'signup', 0, now()),
(6, 'purchase', 100, now());

-- ============================================================================
-- 5. ЗАПРОС БЫСТРОЙ АНАЛИТИКИ ПО ДНЯМ (Через *Merge функции)
-- ============================================================================
SELECT 
    event_date, 
    event_type, 
    uniqMerge(unique_users) AS unique_users, 
    sumMerge(total_points) AS spent_points_sum, 
    countMerge(actions_count) AS actions_cnt
FROM user_events_daily_agg 
GROUP BY event_date, event_type 
ORDER BY event_date, event_type;

-- ============================================================================
-- 6. ЗАПРОС РАСЧЕТА RETENTION В ТРЕБУЕМОМ ФОРМАТЕ
-- ============================================================================
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
FROM user_cohorts;
