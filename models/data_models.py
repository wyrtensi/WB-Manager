# -*- coding: utf-8 -*-
"""
Модели данных для WB Manager
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


@dataclass
class GoodsInfo:
    """Информация о товаре из JSON поля info"""
    brand: str = ""
    name: str = ""
    subject_name: str = ""
    color: str = ""
    adult: bool = False
    no_return: bool = False
    pics_cnt: int = 1
    
    @classmethod
    def from_json(cls, json_str: str) -> "GoodsInfo":
        """Парсинг JSON строки info"""
        try:
            data = json.loads(json_str) if isinstance(json_str, str) else json_str
            return cls(
                brand=data.get("brand", ""),
                name=data.get("name", ""),
                subject_name=data.get("subject_name", ""),
                color=data.get("color", ""),
                adult=bool(data.get("adult", False)),
                no_return=bool(data.get("no_return", False)),
                pics_cnt=data.get("pics_cnt", 1)
            )
        except (json.JSONDecodeError, TypeError):
            return cls()


@dataclass
class Goods:
    """Модель товара (goods_in_pick_point / goods_on_way)"""
    item_uid: str
    buyer_sid: str
    scanned_code: str  # ШК - основной идентификатор для поиска
    encoded_scanned_code: str  # Для генерации QR
    vendor_code: str  # Артикул для получения изображений
    cell: Optional[str] = None
    status: str = ""
    price: int = 0
    price_with_sale: int = 0
    is_paid: int = 0
    priority_order: int = 0
    payment_type: str = ""
    info: Optional[GoodsInfo] = None
    sticker_code: str = ""  # ШК для goods_on_way
    barcode: str = ""  # Штрихкод EAN
    is_on_way: bool = False  # Флаг: товар в пути или на ПВЗ
    
    @property
    def display_barcode(self) -> str:
        """Получить ШК для отображения (scanned_code или sticker_code)"""
        return self.sticker_code if self.is_on_way and self.sticker_code else self.scanned_code
    
    @property
    def price_formatted(self) -> str:
        """Цена с форматированием"""
        return f"{self.price_with_sale / 100:.2f} ₽" if self.price_with_sale else f"{self.price / 100:.2f} ₽"
    
    @property
    def is_payment_required(self) -> bool:
        """Нужна ли оплата при получении"""
        return self.is_paid == 0
    
    @property
    def status_display(self) -> str:
        """Человекочитаемый статус"""
        from config import GOODS_STATUSES
        return GOODS_STATUSES.get(self.status, self.status)


@dataclass
class Buyer:
    """Модель покупателя/клиента"""
    user_sid: str  # Уникальный идентификатор
    mobile: str = ""
    name: str = ""  # Системное имя (обычно пустое)
    user_id: str = ""
    
    # Кастомные поля (хранятся отдельно)
    custom_name: str = ""
    custom_description: str = ""
    custom_photo_path: str = ""
    
    # Связанные данные
    cell: Optional[str] = None
    cell_updated: Optional[datetime] = None
    goods_count: int = 0
    goods_on_way_count: int = 0
    try_on_timestamp: Optional[int] = None
    try_on_order_id: str = ""
    try_on_buyer_code: str = ""
    try_on_is_delivery_from_cancel: bool = False
    try_on_has_unread_warning: bool = False
    try_on_done_forced_sync: bool = False
    
    @property
    def display_name(self) -> str:
        """Имя для отображения (кастомное или системное)"""
        if self.custom_name:
            return self.custom_name
        if self.name:
            return self.name
        return f"Клиент {self.user_sid[:8]}..."
    
    @property
    def mobile_formatted(self) -> str:
        """Телефон с выделенными последними 4 цифрами"""
        mobile_str = str(self.mobile) if self.mobile else ""
        if len(mobile_str) >= 4:
            return f"{mobile_str[:-4]}**{mobile_str[-4:]}**"
        return mobile_str
    
    @property
    def mobile_last4(self) -> str:
        """Последние 4 цифры телефона"""
        mobile_str = str(self.mobile) if self.mobile else ""
        return mobile_str[-4:] if len(mobile_str) >= 4 else mobile_str


@dataclass
class DeliveredOrder:
    """Доставленный заказ с группировкой товаров"""
    order_id: str
    delivery_timestamp: int
    items: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def delivery_date(self) -> str:
        """Дата доставки в читаемом формате"""
        dt = datetime.fromtimestamp(self.delivery_timestamp / 1000)
        return dt.strftime("%d.%m.%Y %H:%M")
    
    @property
    def items_count(self) -> int:
        """Количество товаров в заказе"""
        return len(self.items)


@dataclass 
class SurplusGoods:
    """Излишки (товары без владельца)"""
    goods_uid: str
    scanned_code: str
    decoded_scanned_code: str
    is_error_surplus: bool = False
    cell: Optional[str] = None
    acceptance_timestamp: Optional[int] = None
    is_dbs: bool = False
