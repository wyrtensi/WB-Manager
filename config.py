# -*- coding: utf-8 -*-
"""
Конфигурация приложения WB Manager
"""
import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).parent
DATABASE_DIR = BASE_DIR / "database"

# Путь к основной базе WB Point
WB_POINT_DB_DIR = Path(os.environ.get('APPDATA', '')) / "com.example" / "wb_point_desktop"
DATABASE_PATH = WB_POINT_DB_DIR / "wb_point_db.sqlite"

# Путь для кастомных данных пользователей (фото, имена, описания)
# Используем просто папки в корне, без вложенного wb_manager
CUSTOM_DATA_DIR = BASE_DIR / "custom_data"
CUSTOM_BUYERS_FILE = CUSTOM_DATA_DIR / "custom_buyers.json"
CUSTOM_PHOTOS_DIR = CUSTOM_DATA_DIR / "photos"

# Кэш изображений товаров
IMAGE_CACHE_DIR = BASE_DIR / "cache" / "images"

# Настройки приложения
APP_HOST = "127.0.0.1"
APP_PORT = 5050
DEBUG_MODE = True

# Wildberries API для получения изображений
WB_IMAGE_BASE_URL = "https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{vendor_code}/images/c516x688/{num}.webp"
WB_SMALL_IMAGE_URL = "https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{vendor_code}/images/c246x328/{num}.webp"

# Статусы товаров
GOODS_STATUSES = {
    "GOODS_READY": "Готов к выдаче",
    "GOODS_RECIEVED": "Получен клиентом",
    "GOODS_COURIER_RECEIVED": "Передан курьеру",
    "GOODS_DECLINED": "Отказ",
    "GOODS_ACCEPT_CLIENT_CANCELED": "Отменён клиентом",
    "GOODS_WITHOUT_STATUS": "В пути"
}

# Типы оплаты
PAYMENT_TYPES = {
    "PAYMENT_BY_CASH": "Наличные",
    "PAYMENT_BY_CARD": "Картой"
}

# Создание необходимых директорий
for directory in [CUSTOM_DATA_DIR, CUSTOM_PHOTOS_DIR, IMAGE_CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
