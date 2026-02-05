# -*- coding: utf-8 -*-
"""
Менеджер базы данных SQLite для WB Manager
Обеспечивает доступ к данным wb_point_db.sqlite
"""
import sqlite3
import json
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager
import threading

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATABASE_PATH, CUSTOM_BUYERS_FILE
from models import Goods, GoodsInfo, Buyer, DeliveredOrder, SurplusGoods

TZ_PATTERN = re.compile(r"[+-]\d{2}:?\d{2}$")


class DatabaseManager:
    """Менеджер для работы с SQLite базой данных ПВЗ"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton паттерн для единственного подключения"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._db_path = DATABASE_PATH
        self._custom_data: Dict[str, Dict] = {}
        self._load_custom_data()
        self._initialized = True
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _load_custom_data(self):
        """Загрузка кастомных данных покупателей"""
        if CUSTOM_BUYERS_FILE.exists():
            try:
                with open(CUSTOM_BUYERS_FILE, 'r', encoding='utf-8') as f:
                    self._custom_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._custom_data = {}
        else:
            self._custom_data = {}
    
    def _save_custom_data(self):
        """Сохранение кастомных данных покупателей"""
        CUSTOM_BUYERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CUSTOM_BUYERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._custom_data, f, ensure_ascii=False, indent=2)
    
    # ============== ТОВАРЫ НА ПВЗ (goods_in_pick_point) ==============
    
    def get_goods_at_pickup(self, limit: int = 100, offset: int = 0) -> List[Goods]:
        """Получить товары на ПВЗ"""
        query = """
            SELECT * FROM goods_in_pick_point 
            ORDER BY priority_order DESC, cell 
            LIMIT ? OFFSET ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit, offset))
            return [self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()]
    
    def search_goods_by_barcode(self, barcode: str) -> List[Goods]:
        """Поиск товаров по ШК (scanned_code) на ПВЗ и в пути"""
        results = []
        
        # Поиск на ПВЗ
        query_pickup = """
            SELECT * FROM goods_in_pick_point 
            WHERE scanned_code LIKE ? OR sticker_code LIKE ? OR barcode LIKE ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query_pickup, (f"%{barcode}%", f"%{barcode}%", f"%{barcode}%"))
            results.extend([self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()])
        
        # Поиск в пути (goods_on_way использует shk_code и sticker_code вместо scanned_code)
        query_onway = """
            SELECT * FROM goods_on_way 
            WHERE CAST(shk_code AS TEXT) LIKE ? OR CAST(sticker_code AS TEXT) LIKE ? OR CAST(barcode AS TEXT) LIKE ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query_onway, (f"%{barcode}%", f"%{barcode}%", f"%{barcode}%"))
            results.extend([self._row_to_goods(row, is_on_way=True) for row in cursor.fetchall()])
        
        return results
    
    def search_goods_by_name(self, name: str) -> List[Goods]:
        """Поиск товаров по названию или бренду"""
        results = []
        
        # Поиск на ПВЗ
        query_pickup = """
            SELECT * FROM goods_in_pick_point 
            WHERE json_extract(info, '$.name') LIKE ? 
               OR json_extract(info, '$.brand') LIKE ?
               OR json_extract(info, '$.subject_name') LIKE ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query_pickup, (f"%{name}%", f"%{name}%", f"%{name}%"))
            results.extend([self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()])
        
        # Поиск в пути
        query_onway = """
            SELECT * FROM goods_on_way 
            WHERE json_extract(info, '$.name') LIKE ? 
               OR json_extract(info, '$.brand') LIKE ?
               OR json_extract(info, '$.subject_name') LIKE ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query_onway, (f"%{name}%", f"%{name}%", f"%{name}%"))
            results.extend([self._row_to_goods(row, is_on_way=True) for row in cursor.fetchall()])
        
        return results
        
        return results
    
    def get_goods_by_buyer(self, buyer_sid: str) -> List[Goods]:
        """Получить товары покупателя на ПВЗ (только готовые к выдаче)"""
        query = """
            SELECT * FROM goods_in_pick_point 
            WHERE buyer_sid = ? AND status = 'GOODS_READY'
            ORDER BY priority_order DESC
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (buyer_sid,))
            return [self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()]
    
    def get_all_goods_by_buyer(self, buyer_sid: str) -> List[Goods]:
        """Получить ВСЕ товары покупателя без фильтров"""
        results = []
        # Товары на ПВЗ
        query1 = "SELECT * FROM goods_in_pick_point WHERE buyer_sid = ? ORDER BY priority_order DESC"
        with self.get_connection() as conn:
            cursor = conn.execute(query1, (buyer_sid,))
            results.extend([self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()])
        
        # Товары в пути
        query2 = "SELECT * FROM goods_on_way WHERE buyer_sid = ?"
        with self.get_connection() as conn:
            cursor = conn.execute(query2, (buyer_sid,))
            results.extend([self._row_to_goods(row, is_on_way=True) for row in cursor.fetchall()])
        
        return results
    
    def get_goods_on_way_by_buyer(self, buyer_sid: str) -> List[Goods]:
        """Получить товары покупателя в пути (исключая отклонённые, только за 30 дней)"""
        # status_updated в формате ISO: 2025-07-03T04:06:19Z
        query = """
            SELECT * FROM goods_on_way 
            WHERE buyer_sid = ? 
              AND status != 'GOODS_DECLINED'
              AND date(substr(status_updated, 1, 10)) >= date('now', '-30 days')
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (buyer_sid,))
            return [self._row_to_goods(row, is_on_way=True) for row in cursor.fetchall()]
    
    def get_goods_by_status(self, status: str) -> List[Goods]:
        """Получить товары по статусу"""
        query = """
            SELECT * FROM goods_in_pick_point 
            WHERE status = ?
            ORDER BY priority_order DESC
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (status,))
            return [self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()]
    
    def get_goods_by_cell(self, cell: str) -> List[Goods]:
        """Получить товары в ячейке"""
        query = """
            SELECT * FROM goods_in_pick_point 
            WHERE cell = ?
            ORDER BY priority_order DESC
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (cell,))
            return [self._row_to_goods(row, is_on_way=False) for row in cursor.fetchall()]
    
    # ============== ТОВАРЫ В ПУТИ (goods_on_way) ==============
    
    def get_goods_on_way(self, limit: int = 100, offset: int = 0) -> List[Goods]:
        """Получить товары в пути на ПВЗ (только за последние 30 дней, исключая отклонённые)"""
        # status_updated - это дата в формате ISO (2025-07-03T04:06:19Z)
        query = """
            SELECT * FROM goods_on_way 
            WHERE date(substr(status_updated, 1, 10)) >= date('now', '-30 days')
              AND status != 'GOODS_DECLINED'
            ORDER BY buyer_sid
            LIMIT ? OFFSET ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit, offset))
            return [self._row_to_goods(row, is_on_way=True) for row in cursor.fetchall()]
    
    def count_goods_on_way(self) -> int:
        """Подсчёт товаров в пути (только за последние 30 дней, исключая отклонённые)"""
        query = """
            SELECT COUNT(*) FROM goods_on_way
            WHERE date(substr(status_updated, 1, 10)) >= date('now', '-30 days')
              AND status != 'GOODS_DECLINED'
        """
        with self.get_connection() as conn:
            return conn.execute(query).fetchone()[0]
    
    # ============== ПОКУПАТЕЛИ (buyers) ==============
    
    def get_all_buyers(self, limit: int = 100, offset: int = 0) -> List[Buyer]:
        """Получить список покупателей"""
        query = """
            SELECT b.*, bwc.cell, bwc.status_updated as cell_updated
            FROM buyers b
            LEFT JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            ORDER BY b.user_sid
            LIMIT ? OFFSET ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit, offset))
            return [self._row_to_buyer(row) for row in cursor.fetchall()]
    
    def get_buyers_with_cell(self, limit: int = 100, offset: int = 0) -> List[Buyer]:
        """Получить покупателей с присвоенной ячейкой, отсортированных по номеру ячейки"""
        query = """
            SELECT b.*, bwc.cell, bwc.status_updated as cell_updated
            FROM buyers b
            INNER JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            WHERE bwc.cell IS NOT NULL AND bwc.cell != ''
            ORDER BY CAST(bwc.cell AS INTEGER), bwc.cell
            LIMIT ? OFFSET ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit, offset))
            return [self._row_to_buyer(row) for row in cursor.fetchall()]
    
    def get_buyers_by_cell(self, cell: str, limit: int = 100, offset: int = 0) -> List[Buyer]:
        """Получить покупателей по номеру ячейки (точное или частичное совпадение)"""
        query = """
            SELECT b.*, bwc.cell, bwc.status_updated as cell_updated
            FROM buyers b
            INNER JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            WHERE bwc.cell LIKE ?
            ORDER BY CAST(bwc.cell AS INTEGER), bwc.cell
            LIMIT ? OFFSET ?
        """
        with self.get_connection() as conn:
            # Поиск по началу номера ячейки
            cursor = conn.execute(query, (f"{cell}%", limit, offset))
            return [self._row_to_buyer(row) for row in cursor.fetchall()]
    
    def get_buyers_with_goods_on_way(self, limit: int = 100, offset: int = 0) -> List[Buyer]:
        """Получить покупателей у которых есть товары в пути"""
        query = """
            SELECT DISTINCT b.*, bwc.cell, bwc.status_updated as cell_updated
            FROM buyers b
            LEFT JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            INNER JOIN goods_on_way g ON b.user_sid = g.buyer_sid
            WHERE g.status != 'GOODS_DECLINED'
              AND date(substr(g.status_updated, 1, 10)) >= date('now', '-30 days')
            ORDER BY b.user_sid
            LIMIT ? OFFSET ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit, offset))
            return [self._row_to_buyer(row) for row in cursor.fetchall()]

    def get_buyers_on_try_on(self) -> List[Buyer]:
        """Получить покупателей, отмеченных как на примерке"""
        query = """
            SELECT b.*, bwc.cell, bwc.status_updated as cell_updated,
                   bot.timestamp AS try_on_timestamp,
                   bot.order_id AS try_on_order_id,
                   bot.buyer_code AS try_on_buyer_code,
                   bot.is_delievry_from_cancel AS try_on_is_delivery_from_cancel,
                   bot.has_unread_warning AS try_on_has_unread_warning,
                   bot.done_forced_sync AS try_on_done_forced_sync,
                   COALESCE(ready.ready_count, 0) AS ready_goods_count,
                   COALESCE(onway.onway_count, 0) AS onway_goods_count
            FROM buyers_on_try_on bot
            INNER JOIN buyers b ON bot.buyer_sid = b.user_sid
            LEFT JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            LEFT JOIN (
                SELECT buyer_sid, COUNT(*) AS ready_count
                FROM goods_in_pick_point
                WHERE status = 'GOODS_READY'
                GROUP BY buyer_sid
            ) ready ON ready.buyer_sid = b.user_sid
            LEFT JOIN (
                SELECT buyer_sid, COUNT(*) AS onway_count
                FROM goods_on_way
                WHERE status != 'GOODS_DECLINED'
                  AND date(substr(status_updated, 1, 10)) >= date('now', '-30 days')
                GROUP BY buyer_sid
            ) onway ON onway.buyer_sid = b.user_sid
            ORDER BY bot.timestamp DESC
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query)
            buyers = []
            for row in cursor.fetchall():
                buyer = self._row_to_buyer(row)
                buyer.goods_count = self._safe_get(row, 'ready_goods_count', 0) or 0
                buyer.goods_on_way_count = self._safe_get(row, 'onway_goods_count', 0) or 0
                buyer.try_on_timestamp = self._safe_get(row, 'try_on_timestamp')
                buyer.try_on_order_id = self._safe_get(row, 'try_on_order_id', '') or ''
                buyer.try_on_buyer_code = self._safe_get(row, 'try_on_buyer_code', '') or ''
                buyer.try_on_is_delivery_from_cancel = bool(self._safe_get(row, 'try_on_is_delivery_from_cancel', 0))
                buyer.try_on_has_unread_warning = bool(self._safe_get(row, 'try_on_has_unread_warning', 0))
                buyer.try_on_done_forced_sync = bool(self._safe_get(row, 'try_on_done_forced_sync', 0))
                buyers.append(buyer)
            return buyers
    
    def get_buyer_by_sid(self, user_sid: str) -> Optional[Buyer]:
        """Получить покупателя по user_sid"""
        query = """
            SELECT b.*, bwc.cell, bwc.status_updated as cell_updated
            FROM buyers b
            LEFT JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            WHERE b.user_sid = ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (user_sid,))
            row = cursor.fetchone()
            if row:
                buyer = self._row_to_buyer(row)
                # Подсчёт товаров покупателя (только готовые к выдаче)
                count_query = "SELECT COUNT(*) FROM goods_in_pick_point WHERE buyer_sid = ? AND status = 'GOODS_READY'"
                buyer.goods_count = conn.execute(count_query, (user_sid,)).fetchone()[0]
                return buyer
        return None
    
    def search_buyers(self, query_str: str) -> List[Buyer]:
        """Поиск покупателей по телефону, имени или user_sid"""
        query = """
            SELECT b.*, bwc.cell, bwc.status_updated as cell_updated
            FROM buyers b
            LEFT JOIN buyers_with_cells bwc ON b.user_sid = bwc.user_sid
            WHERE CAST(b.mobile AS TEXT) LIKE ? 
               OR b.name LIKE ? 
               OR b.user_sid LIKE ?
            LIMIT 50
        """
        search_pattern = f"%{query_str}%"
        with self.get_connection() as conn:
            cursor = conn.execute(query, (search_pattern, search_pattern, search_pattern))
            buyers = [self._row_to_buyer(row) for row in cursor.fetchall()]
        
        # Дополнительно ищем по custom_name
        query_lower = query_str.lower()
        for user_sid, data in self._custom_data.items():
            custom_name = data.get('custom_name', '')
            if custom_name and query_lower in custom_name.lower():
                # Проверяем, что не дублируется
                if not any(b.user_sid == user_sid for b in buyers):
                    buyer = self.get_buyer_by_sid(user_sid)
                    if buyer:
                        buyers.append(buyer)
        
        return buyers[:50]
    
    def update_buyer_custom_data(self, user_sid: str, 
                                  custom_name: str = None,
                                  custom_description: str = None,
                                  custom_photo_path: str = None) -> bool:
        """Обновить кастомные данные покупателя"""
        if user_sid not in self._custom_data:
            self._custom_data[user_sid] = {}
        
        if custom_name is not None:
            self._custom_data[user_sid]["custom_name"] = custom_name
        if custom_description is not None:
            self._custom_data[user_sid]["custom_description"] = custom_description
        if custom_photo_path is not None:
            self._custom_data[user_sid]["custom_photo_path"] = custom_photo_path
        
        self._save_custom_data()
        return True
    
    # ============== ИСТОРИЯ ДОСТАВОК (delivered_goods) ==============
    
    def search_delivered_goods(self, barcode: str) -> List[Dict]:
        """Поиск в истории доставок по ШК или goods_uid с полной информацией о товаре"""
        # Основной запрос с JOIN для получения всей информации
        query = """
            SELECT 
                d.goods_uid,
                d.order_id,
                d.delivery_unix_timestamp,
                g.status_updated as status_updated,
                g.scanned_code,
                g.vendor_code,
                g.info,
                g.price,
                g.price_with_sale,
                g.buyer_sid
            FROM delivered_goods d
            LEFT JOIN goods_in_pick_point g ON d.goods_uid = g.item_uid
            WHERE d.goods_uid LIKE ? 
               OR d.order_id LIKE ?
               OR g.scanned_code LIKE ? 
               OR CAST(g.shk_code AS TEXT) LIKE ?
            ORDER BY d.delivery_unix_timestamp DESC
            LIMIT 100
        """
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, (f"%{barcode}%", f"%{barcode}%", f"%{barcode}%", f"%{barcode}%"))
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # Парсим info JSON
                if item.get('info'):
                    try:
                        item['info'] = json.loads(item['info']) if isinstance(item['info'], str) else item['info']
                    except Exception:
                        item['info'] = {}
                delivery_ts = self._extract_delivery_timestamp(item)
                if delivery_ts is not None:
                    item['delivery_timestamp'] = delivery_ts
                results.append(item)
            return results
    
    def get_order_by_goods_uid(self, goods_uid: str) -> List[Dict]:
        """Получить весь заказ по goods_uid одного товара"""
        # Сначала находим buyer_sid и время выдачи этого товара
        find_query = """
            SELECT d.delivery_unix_timestamp, g.buyer_sid
            FROM delivered_goods d
            LEFT JOIN goods_in_pick_point g ON d.goods_uid = g.item_uid
            WHERE d.goods_uid = ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(find_query, (goods_uid,))
            row = cursor.fetchone()
            if not row:
                return []
            
            timestamp = row['delivery_unix_timestamp']
            buyer_sid = row['buyer_sid']
            
            # Теперь находим все товары этого клиента, выданные в ту же минуту
            order_query = """
                SELECT 
                    d.goods_uid,
                    d.order_id,
                    d.delivery_unix_timestamp,
                    g.status_updated as status_updated,
                    g.scanned_code,
                    g.vendor_code,
                    g.info,
                    g.price,
                    g.price_with_sale,
                    g.buyer_sid,
                    b.name as buyer_name,
                    b.mobile as buyer_mobile
                FROM delivered_goods d
                LEFT JOIN goods_in_pick_point g ON d.goods_uid = g.item_uid
                LEFT JOIN buyers b ON g.buyer_sid = b.user_sid
                WHERE g.buyer_sid = ? 
                  AND d.delivery_unix_timestamp >= ? - 60
                  AND d.delivery_unix_timestamp <= ? + 60
                ORDER BY d.delivery_unix_timestamp DESC
            """
            cursor = conn.execute(order_query, (buyer_sid, timestamp, timestamp))
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                if item.get('info'):
                    try:
                        item['info'] = json.loads(item['info']) if isinstance(item['info'], str) else item['info']
                    except Exception:
                        item['info'] = {}
                delivery_ts = self._extract_delivery_timestamp(item)
                if delivery_ts is not None:
                    item['delivery_timestamp'] = delivery_ts
                results.append(item)
            return results
    
    def get_orders_by_order_id(self, order_id: str) -> List[Dict]:
        """Получить все товары заказа по order_id"""
        query = """
            SELECT * FROM delivered_goods 
            WHERE order_id = ?
            ORDER BY delivery_unix_timestamp DESC
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (order_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_deliveries(self, limit: int = 50) -> List[DeliveredOrder]:
        """Получить последние доставки с группировкой по order_id"""
        query = """
            SELECT order_id, MAX(delivery_unix_timestamp) as delivery_timestamp,
                   COUNT(*) as items_count
            FROM delivered_goods 
            GROUP BY order_id
            ORDER BY delivery_timestamp DESC
            LIMIT ?
        """
        orders = []
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit,))
            for row in cursor.fetchall():
                order = DeliveredOrder(
                    order_id=row["order_id"],
                    delivery_timestamp=row["delivery_timestamp"],
                    items=[]
                )
                # Получаем товары заказа
                items_cursor = conn.execute(
                    "SELECT * FROM delivered_goods WHERE order_id = ?",
                    (row["order_id"],)
                )
                order.items = [dict(item) for item in items_cursor.fetchall()]
                orders.append(order)
        return orders
    
    # ============== ИЗЛИШКИ (surplus_goods) ==============
    
    def get_surplus_goods(self) -> List[SurplusGoods]:
        """Получить все излишки"""
        query = "SELECT * FROM surplus_goods ORDER BY acceptance_unix_timestamp DESC"
        with self.get_connection() as conn:
            cursor = conn.execute(query)
            return [self._row_to_surplus(row) for row in cursor.fetchall()]
    
    def get_surplus_count(self) -> int:
        """Получить количество излишков"""
        query = "SELECT COUNT(*) FROM surplus_goods"
        with self.get_connection() as conn:
            return conn.execute(query).fetchone()[0]
    
    def clear_surplus_goods(self) -> bool:
        """Очистить таблицу излишков"""
        query = "DELETE FROM surplus_goods"
        with self.get_connection() as conn:
            conn.execute(query)
            conn.commit()
            return True
    
    def delete_surplus_item(self, goods_uid: str) -> bool:
        """Удалить один излишек по goods_uid"""
        query = "DELETE FROM surplus_goods WHERE goods_uid = ?"
        with self.get_connection() as conn:
            cursor = conn.execute(query, (goods_uid,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_vendor_codes(self) -> List[str]:
        """Получить все уникальные vendor_code из всех таблиц с товарами"""
        query = """
            SELECT DISTINCT vendor_code FROM (
                SELECT vendor_code FROM goods_in_pick_point WHERE vendor_code IS NOT NULL AND vendor_code != ''
                UNION
                SELECT vendor_code FROM goods_on_way WHERE vendor_code IS NOT NULL AND vendor_code != ''
            )
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query)
            return [row[0] for row in cursor.fetchall()]
    
    def get_delivered_goods(self, limit: int = 100) -> List[Dict]:
        """Получить список выданных товаров с полной информацией"""
        query = """
            SELECT 
                d.goods_uid,
                d.order_id,
                d.delivery_unix_timestamp,
                g.status_updated as status_updated,
                g.scanned_code,
                g.vendor_code,
                g.info,
                g.price,
                g.price_with_sale,
                g.buyer_sid,
                b.name as buyer_name,
                b.mobile as buyer_mobile
            FROM delivered_goods d
            LEFT JOIN goods_in_pick_point g ON d.goods_uid = g.item_uid
            LEFT JOIN buyers b ON g.buyer_sid = b.user_sid
            ORDER BY d.delivery_unix_timestamp DESC
            LIMIT ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (limit,))
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # Парсим info JSON
                if item.get('info'):
                    try:
                        item['info'] = json.loads(item['info']) if isinstance(item['info'], str) else item['info']
                    except Exception:
                        item['info'] = {}
                # Конвертируем timestamp
                delivery_ts = self._extract_delivery_timestamp(item)
                if delivery_ts is not None:
                    item['delivery_timestamp'] = delivery_ts
                # Применяем custom_name если есть
                buyer_sid = item.get('buyer_sid')
                if buyer_sid and buyer_sid in self._custom_data:
                    custom_name = self._custom_data[buyer_sid].get('custom_name')
                    if custom_name:
                        item['buyer_name'] = custom_name
                results.append(item)
            return results
    
    def get_buyer_delivered_goods(self, user_sid: str) -> List[Dict]:
        """Получить историю заказов клиента"""
        query = """
            SELECT 
                d.goods_uid,
                d.order_id,
                d.delivery_unix_timestamp,
                g.status_updated as status_updated,
                g.scanned_code,
                g.vendor_code,
                g.info,
                g.price,
                g.price_with_sale
            FROM delivered_goods d
            INNER JOIN goods_in_pick_point g ON d.goods_uid = g.item_uid
            WHERE g.buyer_sid = ?
            ORDER BY d.delivery_unix_timestamp DESC
            LIMIT 100
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (user_sid,))
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                if item.get('info'):
                    try:
                        item['info'] = json.loads(item['info']) if isinstance(item['info'], str) else item['info']
                    except Exception:
                        item['info'] = {}
                delivery_ts = self._extract_delivery_timestamp(item)
                if delivery_ts is not None:
                    item['delivery_timestamp'] = delivery_ts
                results.append(item)
            return results
    
    # ============== СТАТИСТИКА ==============
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить общую статистику ПВЗ"""
        stats = {}
        with self.get_connection() as conn:
            # Товары на ПВЗ (только GOODS_READY - готовые к выдаче)
            stats["goods_at_pickup"] = conn.execute(
                "SELECT COUNT(*) FROM goods_in_pick_point WHERE status = 'GOODS_READY'"
            ).fetchone()[0]
            
            # Товары в пути (только за последние 30 дней, исключая DECLINED)
            stats["goods_on_way"] = conn.execute(
                "SELECT COUNT(*) FROM goods_on_way WHERE date(substr(status_updated, 1, 10)) >= date('now', '-30 days') AND status != 'GOODS_DECLINED'"
            ).fetchone()[0]
            
            # Всего покупателей
            stats["total_buyers"] = conn.execute(
                "SELECT COUNT(*) FROM buyers"
            ).fetchone()[0]
            
            # Покупатели на примерке
            stats["buyers_on_try_on"] = conn.execute(
                "SELECT COUNT(*) FROM buyers_on_try_on"
            ).fetchone()[0]
            
            # Излишки
            stats["surplus_count"] = conn.execute(
                "SELECT COUNT(*) FROM surplus_goods"
            ).fetchone()[0]
            
            # Товары по статусам
            status_query = """
                SELECT status, COUNT(*) as count 
                FROM goods_in_pick_point 
                GROUP BY status
            """
            stats["by_status"] = {
                row["status"]: row["count"] 
                for row in conn.execute(status_query).fetchall()
            }
            
            # Занятые ячейки
            stats["occupied_cells"] = conn.execute(
                "SELECT COUNT(DISTINCT cell) FROM goods_in_pick_point WHERE cell IS NOT NULL AND status = 'GOODS_READY'"
            ).fetchone()[0]
        
        return stats
    
    # ============== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==============
    
    def _safe_get(self, row: sqlite3.Row, key: str, default=None):
        """Безопасное получение значения из sqlite3.Row"""
        try:
            value = row[key]
            return value if value is not None else default
        except (IndexError, KeyError):
            return default

    def _parse_status_timestamp(self, value: Optional[str]) -> Optional[int]:
        """Преобразование status_updated в Unix-время (мс)."""
        if not value:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        normalized = normalized.replace(' ', 'T')
        if normalized.endswith('Z'):
            normalized = normalized[:-1] + '+00:00'
        elif not TZ_PATTERN.search(normalized):
            normalized = f"{normalized}+03:00"
        try:
            dt = datetime.fromisoformat(normalized)
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None

    def _extract_delivery_timestamp(self, row: Dict[str, Any]) -> Optional[int]:
        """Определение времени выдачи с приоритетом status_updated."""
        status_updated = row.get('status_updated')
        ts = self._parse_status_timestamp(status_updated)
        if ts:
            return ts
        delivery_unix = row.get('delivery_unix_timestamp')
        if delivery_unix is None:
            return None
        try:
            delivery_unix = int(delivery_unix)
        except (TypeError, ValueError):
            return None
        if delivery_unix >= 10**12:
            return delivery_unix
        return delivery_unix * 1000
    
    def _row_to_goods(self, row: sqlite3.Row, is_on_way: bool = False) -> Goods:
        """Преобразование строки БД в объект Goods"""
        info = None
        info_data = self._safe_get(row, "info")
        if info_data:
            info = GoodsInfo.from_json(info_data)
        
        # goods_on_way использует shk_code вместо scanned_code
        scanned_code = self._safe_get(row, "scanned_code", "")
        if not scanned_code and is_on_way:
            shk_code = self._safe_get(row, "shk_code", "")
            scanned_code = str(shk_code) if shk_code else ""
        
        # encoded_scanned_code может отсутствовать в goods_on_way
        raw_encoded_code = self._safe_get(row, "encoded_scanned_code", "")
        encoded_scanned_code = str(raw_encoded_code) if raw_encoded_code else ""
        
        # vendor_code может быть числом
        vendor_code = self._safe_get(row, "vendor_code", "")
        vendor_code = str(vendor_code) if vendor_code else ""
        
        # sticker_code тоже может быть числом
        sticker_code = self._safe_get(row, "sticker_code", "")
        sticker_code = str(sticker_code) if sticker_code else ""
        
        # barcode (штрихкод EAN)
        barcode = self._safe_get(row, "barcode", "")
        barcode = str(barcode) if barcode else ""
        
        return Goods(
            item_uid=row["item_uid"],
            buyer_sid=row["buyer_sid"],
            scanned_code=str(scanned_code) if scanned_code else "",
            encoded_scanned_code=encoded_scanned_code,
            vendor_code=vendor_code,
            cell=self._safe_get(row, "cell"),
            status=self._safe_get(row, "status", ""),
            price=self._safe_get(row, "price", 0) or 0,
            price_with_sale=self._safe_get(row, "price_with_sale", 0) or 0,
            is_paid=self._safe_get(row, "is_paid", 0) or 0,
            priority_order=self._safe_get(row, "priority_order", 0) or 0,
            payment_type=self._safe_get(row, "payment_type", ""),
            info=info,
            sticker_code=sticker_code,
            barcode=barcode,
            is_on_way=is_on_way
        )
    
    def _row_to_buyer(self, row: sqlite3.Row) -> Buyer:
        """Преобразование строки БД в объект Buyer"""
        user_sid = row["user_sid"]
        custom = self._custom_data.get(user_sid, {})
        
        return Buyer(
            user_sid=user_sid,
            mobile=self._safe_get(row, "mobile", ""),
            name=self._safe_get(row, "name", ""),
            user_id=self._safe_get(row, "user_id", ""),
            custom_name=custom.get("custom_name", ""),
            custom_description=custom.get("custom_description", ""),
            custom_photo_path=custom.get("custom_photo_path", ""),
            cell=self._safe_get(row, "cell"),
            cell_updated=self._safe_get(row, "cell_updated")
        )
    
    def _row_to_surplus(self, row: sqlite3.Row) -> SurplusGoods:
        """Преобразование строки БД в объект SurplusGoods"""
        return SurplusGoods(
            goods_uid=row["goods_uid"],
            scanned_code=self._safe_get(row, "scanned_code", ""),
            decoded_scanned_code=self._safe_get(row, "decoded_scanned_code", ""),
            is_error_surplus=bool(self._safe_get(row, "is_error_surplus", 0)),
            cell=self._safe_get(row, "cell"),
            acceptance_timestamp=self._safe_get(row, "acceptance_unix_timestamp"),
            is_dbs=bool(self._safe_get(row, "is_dbs", 0))
        )


# Глобальный экземпляр менеджера БД
db = DatabaseManager()
