import json
from datetime import datetime, timedelta

from pymongo import MongoClient


def archive_inactive_users():
    """
    Архивирует пользователей, которые:
    1. Зарегистрировались более 30 дней назад
    2. Не проявляли активности последние 14 дней
    """
    # Подключение к MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client["my_database"]
    source_collection = db["user_events"]
    archive_collection = db["archived_users"]

    # Пороговые даты
    now = datetime.now()
    registration_threshold = now - timedelta(days=30)  # более 30 дней назад
    activity_threshold = now - timedelta(days=14)  # не активны последние 14 дней

    # Aggregation pipeline: ищем user_id, подходящих под критерии
    pipeline = [
        {
            "$group": {
                "_id": "$user_id",
                "last_activity": {"$max": "$event_time"},
                "registration_date": {"$first": "$user_info.registration_date"},
            }
        },
        {
            "$match": {
                "registration_date": {"$lt": registration_threshold},
                "last_activity": {"$lt": activity_threshold},
            }
        },
    ]

    # Получаем список неактивных user_id
    inactive_users = list(source_collection.aggregate(pipeline))
    inactive_user_ids = [user["_id"] for user in inactive_users]

    archived_count = 0

    if inactive_user_ids:
        # Находим все документы этих пользователей
        users_to_archive = list(
            source_collection.find({"user_id": {"$in": inactive_user_ids}})
        )

        # Архивируем (вставляем в новую коллекцию)
        if users_to_archive:
            # Преобразуем ObjectId в строки для корректной сериализации в JSON
            archive_collection.insert_many(users_to_archive)

            # Удаляем из исходной коллекции
            source_collection.delete_many({"user_id": {"$in": inactive_user_ids}})

            archived_count = len(users_to_archive)

    # Формируем отчёт
    report = {
        "date": now.strftime("%Y-%m-%d"),
        "archived_users_count": len(inactive_user_ids),
        "archived_documents_count": archived_count,
        "archived_user_ids": inactive_user_ids,
        "registration_threshold": registration_threshold.isoformat(),
        "activity_threshold": activity_threshold.isoformat(),
    }

    # Сохраняем отчёт в JSON
    report_filename = f"{now.strftime('%Y-%m-%d')}.json"
    with open(report_filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"✅ Отчёт сохранён: {report_filename}")
    print(f"📊 Архивировано пользователей: {len(inactive_user_ids)}")
    print(f"📄 Архивировано документов: {archived_count}")

    client.close()


if __name__ == "__main__":
    archive_inactive_users()
