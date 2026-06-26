from pymongo import MongoClient
from pprint import pprint

# Подключение к MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["alcomarket"]
products = db["products"]

print("\n📦 Все товары:")
for doc in products.find():
    pprint(doc)

print("\n🍷 Вина с рейтингом сомелье > 4.5:")
for doc in products.find({"type": "wine", "rating.sommelier": {"$gt": 4.5}}):
    pprint(doc)

print("\n📑 Только имя и цена всех товаров:")
for doc in products.find({}, {"name": 1, "price": 1, "_id": 0}):
    pprint(doc)

print("\n🌍 Уникальные страны происхождения:")
pprint(products.distinct("country"))

print("\n📊 Средняя цена пива по странам:")
pipeline = [
    {"$match": {"type": "beer"}},
    {"$group": {"_id": "$country", "avgPrice": {"$avg": "$price"}}},
    {"$sort": {"avgPrice": -1}}
]
for doc in products.aggregate(pipeline):
    pprint(doc)
