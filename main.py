# -*- coding: utf-8 -*-
"""
WB Manager - Главное приложение
Веб-интерфейс для управления ПВЗ Wildberries
"""
import sys
import json
import subprocess
import re
import os
import ctypes
import threading
from pathlib import Path
from datetime import datetime
import time

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, render_template, jsonify, request, send_file, abort, redirect

from config import APP_HOST, APP_PORT, DEBUG_MODE, CUSTOM_PHOTOS_DIR, GOODS_STATUSES
from database.database_manager import db
from api.wb_api import wb_api
from utils.qr_generator import qr_generator
from utils.tts_manager import TTSManager
from utils.bot_manager import BotManager
from utils.tray_icon import TrayIconManager
from models import Goods


app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Инициализация менеджеров
tts_manager = TTSManager()
bot_manager = BotManager(Path(__file__).parent / 'telegram_bot')
SOUNDS_DIR = Path(__file__).parent / 'sounds'
TARGET_SOUNDS_DIR = Path(r"C:\Program Files (x86)\WB_PVZ\data\flutter_assets\assets\sounds")
METADATA_FILE = SOUNDS_DIR / 'metadata.json'

def load_metadata():
    if METADATA_FILE.exists():
        try:
            return json.loads(METADATA_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}

def save_metadata(data):
    METADATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

# Кэш для часто запрашиваемых данных
_stats_cache = {'data': None, 'time': 0}
_STATS_CACHE_TTL = 5  # секунд

# Активные загрузки (user_sid)
active_downloads = set()
# Прогресс загрузки (user_sid -> dict)
download_progress = {}


def auto_start_bot_if_needed():
    """Start Telegram bot on launch unless autostart is disabled."""
    try:
        config = bot_manager.get_config()
    except Exception:
        config = {}

    if config.get('skip_autostart'):
        print("[Bot] Автозапуск отключён настройкой.")
        return

    success, message = bot_manager.start()
    status = "успех" if success else "ошибка"
    print(f"[Bot] Автозапуск: {status} ({message})")


# ============== JINJA ФИЛЬТРЫ ==============

@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    """Конвертация Unix timestamp в читаемую дату"""
    if not timestamp:
        return '-'
    try:
        dt = datetime.fromtimestamp(int(timestamp))
        return dt.strftime('%d.%m.%Y %H:%M')
    except Exception:
        return '-'


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============

def add_image_url_to_dict(item: dict) -> dict:
    """Добавить URL картинки в словарь товара/заказа, если есть в кэше"""
    vendor_code = item.get('vendor_code')
    if vendor_code:
        # Проверяем наличие в кэше
        cache_path = wb_api.get_cached_image_path(str(vendor_code), 1)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            item['image_url'] = f"/api/cached_image/{vendor_code}?size=small&num=1"
        else:
            item['image_url'] = None
    else:
        item['image_url'] = None
    return item


def goods_to_dict(goods: Goods) -> dict:
    """Преобразование объекта товара в словарь для JSON"""
    image_url = None
    if goods.vendor_code:
        # Проверяем наличие в кэше перед тем как отдавать ссылку
        # Чтобы избежать 404 ошибок на фронтенде
        cache_path = wb_api.get_cached_image_path(str(goods.vendor_code), 1)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            image_url = f"/api/cached_image/{goods.vendor_code}?size=small&num=1"

    d = {
        'item_uid': goods.item_uid,
        'buyer_sid': goods.buyer_sid,
        'scanned_code': goods.scanned_code,
        'encoded_scanned_code': goods.encoded_scanned_code,
        'vendor_code': goods.vendor_code,
        'cell': goods.cell,
        'status': goods.status,
        'status_display': GOODS_STATUSES.get(goods.status, goods.status),
        'price': goods.price,
        'price_with_sale': goods.price_with_sale,
        'is_paid': goods.is_paid,
        'payment_type': goods.payment_type,
        'sticker_code': goods.sticker_code,
        'barcode': goods.barcode,
        'is_on_way': goods.is_on_way,
        'image_url': image_url
    }
    
    if goods.info:
        d['info'] = {
            'brand': goods.info.brand,
            'name': goods.info.name,
            'subject_name': goods.info.subject_name,
            'color': goods.info.color,
            'adult': goods.info.adult,
            'no_return': goods.info.no_return,
            'pics_cnt': goods.info.pics_cnt
        }
    else:
        d['info'] = None
    
    return d


def buyer_to_dict(buyer) -> dict:
    """Преобразование объекта покупателя в словарь"""
    try_on_payload = None
    if getattr(buyer, 'try_on_timestamp', None):
        try_on_payload = {
            'timestamp': buyer.try_on_timestamp,
            'order_id': getattr(buyer, 'try_on_order_id', ''),
            'buyer_code': getattr(buyer, 'try_on_buyer_code', ''),
            'is_from_cancel': getattr(buyer, 'try_on_is_delivery_from_cancel', False),
            'has_unread_warning': getattr(buyer, 'try_on_has_unread_warning', False),
            'done_forced_sync': getattr(buyer, 'try_on_done_forced_sync', False)
        }

    return {
        'user_sid': buyer.user_sid,
        'mobile': buyer.mobile,
        'name': buyer.name,
        'user_id': buyer.user_id,
        'custom_name': buyer.custom_name,
        'custom_description': buyer.custom_description,
        'custom_photo_path': buyer.custom_photo_path,
        'cell': buyer.cell,
        'goods_count': buyer.goods_count,
        'display_name': buyer.display_name,
        'mobile_last4': buyer.mobile_last4,
        'goods_on_way_count': getattr(buyer, 'goods_on_way_count', 0),
        'ready_goods_count': buyer.goods_count,
        'try_on': try_on_payload
    }


# ============== СТРАНИЦЫ ==============

@app.route('/')
def index():
    """Главная страница - обзор"""
    return render_template('index.html')


@app.route('/goods')
def goods_page():
    """Страница товаров на ПВЗ"""
    return render_template('goods.html')


@app.route('/goods/on-way')
def goods_onway_page():
    """Страница товаров в пути"""
    return render_template('goods.html')


@app.route('/buyers')
def buyers_page():
    """Страница списка клиентов"""
    return render_template('buyers.html')


@app.route('/buyer/<user_sid>')
def buyer_profile_page(user_sid: str):
    """Страница профиля клиента"""
    buyer = db.get_buyer_by_sid(user_sid)
    if not buyer:
        abort(404)
    
    goods_pickup = db.get_goods_by_buyer(user_sid)
    goods_onway = db.get_goods_on_way_by_buyer(user_sid)
    goods_all = db.get_all_goods_by_buyer(user_sid)
    delivered = db.get_buyer_delivered_goods(user_sid)
    
    # Преобразуем товары в словари с URL изображений
    goods_pickup_dicts = [goods_to_dict(g) for g in goods_pickup]
    goods_onway_dicts = [goods_to_dict(g) for g in goods_onway]
    goods_all_dicts = [goods_to_dict(g) for g in goods_all]
    
    return render_template('buyer_profile.html', 
                           buyer=buyer,
                           goods_pickup=goods_pickup_dicts,
                           goods_onway=goods_onway_dicts,
                           goods_all=goods_all_dicts,
                           delivered=delivered)


@app.route('/history')
def history_page():
    """Страница истории доставок"""
    return render_template('history.html')


@app.route('/surplus')
def surplus_page():
    """Страница излишков"""
    return render_template('surplus.html')


@app.route('/voiceover')
def voiceover_page():
    """Страница озвучки"""
    return render_template('voiceover.html')


# ============== API ENDPOINTS ==============

@app.route('/api/stats')
def api_stats():
    """Получить статистику ПВЗ с кэшированием"""
    now = time.time()
    
    # Используем кэш если данные свежие
    if _stats_cache['data'] and (now - _stats_cache['time']) < _STATS_CACHE_TTL:
        return jsonify(_stats_cache['data'])
    
    stats = db.get_statistics()
    _stats_cache['data'] = stats
    _stats_cache['time'] = now
    return jsonify(stats)


@app.route('/api/goods/pickup')
def api_goods_pickup():
    """Получить товары на ПВЗ"""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    status = request.args.get('status', None)
    
    if status:
        goods = db.get_goods_by_status(status)
    else:
        goods = db.get_goods_at_pickup(limit, offset)
    
    return jsonify({
        'goods': [goods_to_dict(g) for g in goods],
        'count': len(goods)
    })


@app.route('/api/goods/on-way')
def api_goods_onway():
    """Получить товары в пути"""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    goods = db.get_goods_on_way(limit, offset)
    
    return jsonify({
        'goods': [goods_to_dict(g) for g in goods],
        'count': len(goods)
    })


@app.route('/api/goods/by-cell/<cell>')
def api_goods_by_cell(cell: str):
    """Получить товары в ячейке"""
    goods = db.get_goods_by_cell(cell)
    return jsonify({
        'goods': [goods_to_dict(g) for g in goods],
        'count': len(goods)
    })


@app.route('/api/search')
def api_search():
    """Универсальный поиск"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')
    
    if len(query) < 2:
        return jsonify({'goods': [], 'buyers': [], 'delivered': []})
    
    result = {
        'goods': [],
        'buyers': [],
        'delivered': []
    }
    
    # Поиск товаров (по ШК и по названию)
    if search_type in ('all', 'goods'):
        goods = db.search_goods_by_barcode(query)
        # Если по ШК не нашли - ищем по названию
        if not goods:
            goods = db.search_goods_by_name(query)
        result['goods'] = [goods_to_dict(g) for g in goods[:20]]
    
    # Поиск клиентов
    if search_type in ('all', 'buyers'):
        buyers = db.search_buyers(query)
        result['buyers'] = [buyer_to_dict(b) for b in buyers[:20]]
    
    # Поиск в истории
    if search_type in ('all', 'delivered'):
        delivered = db.search_delivered_goods(query)
        # Добавляем картинки
        result['delivered'] = [add_image_url_to_dict(d) for d in delivered[:20]]
    
    return jsonify(result)


@app.route('/api/search/goods')
def api_search_goods():
    """Поиск товаров по названию или ШК"""
    query = request.args.get('q', '').strip()
    search_by = request.args.get('by', 'all')  # all, name, barcode
    
    if len(query) < 2:
        return jsonify({'goods': [], 'count': 0})
    
    goods = []
    
    if search_by in ('all', 'barcode'):
        goods.extend(db.search_goods_by_barcode(query))
    
    if search_by in ('all', 'name') and len(goods) < 50:
        # Добавляем поиск по названию если не нашли по ШК
        name_goods = db.search_goods_by_name(query)
        # Исключаем дубликаты
        existing_uids = {g.item_uid for g in goods}
        for g in name_goods:
            if g.item_uid not in existing_uids:
                goods.append(g)
    
    return jsonify({
        'goods': [goods_to_dict(g) for g in goods[:50]],
        'count': len(goods)
    })


@app.route('/api/buyers')
def api_buyers():
    """Получить список клиентов"""
    limit = request.args.get('limit', 30, type=int)
    offset = request.args.get('offset', 0, type=int)
    query = request.args.get('q', '').strip()
    cell_query = request.args.get('cell', '').strip()
    filter_type = request.args.get('filter', 'all')
    
    if filter_type == 'try-on':
        buyers = db.get_buyers_on_try_on()
        if query:
            q = query.lower()
            buyers = [
                b for b in buyers
                if (b.display_name and q in b.display_name.lower())
                or (b.mobile and q in str(b.mobile))
                or (b.user_sid and q in str(b.user_sid))
            ]
        if cell_query:
            buyers = [b for b in buyers if b.cell and cell_query in str(b.cell)]
        return jsonify({
            'buyers': [buyer_to_dict(b) for b in buyers],
            'count': len(buyers),
            'has_more': False
        })
    
    if cell_query:
        # Поиск по номеру ячейки
        buyers = db.get_buyers_by_cell(cell_query, limit, offset)
    elif query:
        buyers = db.search_buyers(query)
    elif filter_type == 'with-cell':
        buyers = db.get_buyers_with_cell(limit, offset)
    elif filter_type == 'waiting':
        buyers = db.get_buyers_with_goods_on_way(limit, offset)
    else:
        buyers = db.get_all_buyers(limit, offset)
    
    return jsonify({
        'buyers': [buyer_to_dict(b) for b in buyers],
        'count': len(buyers),
        'has_more': len(buyers) == limit
    })


@app.route('/api/buyer/<user_sid>')
def api_buyer(user_sid: str):
    """Получить данные клиента"""
    buyer = db.get_buyer_by_sid(user_sid)
    if not buyer:
        return jsonify({'error': 'Клиент не найден'}), 404
    
    return jsonify(buyer_to_dict(buyer))


@app.route('/api/buyer/<user_sid>/goods')
def api_buyer_goods(user_sid: str):
    """Получить товары клиента по типу"""
    goods_type = request.args.get('type', 'ready')
    if goods_type == 'onway':
        goods = db.get_goods_on_way_by_buyer(user_sid)
    elif goods_type == 'all':
        goods = db.get_all_goods_by_buyer(user_sid)
    else:
        goods = db.get_goods_by_buyer(user_sid)
    return jsonify({'goods': [goods_to_dict(g) for g in goods]})


@app.route('/api/buyer/<user_sid>/update', methods=['POST'])
def api_buyer_update(user_sid: str):
    """Обновить кастомные данные клиента"""
    data = request.get_json()
    
    db.update_buyer_custom_data(
        user_sid,
        custom_name=data.get('custom_name'),
        custom_description=data.get('custom_description')
    )
    
    return jsonify({'success': True})


@app.route('/api/buyer/<user_sid>/photo', methods=['POST'])
def api_buyer_photo_upload(user_sid: str):
    """Загрузить фото клиента"""
    if 'photo' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'Пустой файл'}), 400
    
    # Сохраняем фото
    ext = Path(file.filename).suffix or '.jpg'
    photo_path = CUSTOM_PHOTOS_DIR / f"{user_sid}{ext}"
    file.save(photo_path)
    
    # Обновляем запись
    db.update_buyer_custom_data(user_sid, custom_photo_path=str(photo_path))
    
    return jsonify({'success': True, 'path': str(photo_path)})


@app.route('/api/buyer-photo/<user_sid>')
def api_buyer_photo(user_sid: str):
    """Получить фото клиента"""
    buyer = db.get_buyer_by_sid(user_sid)
    if not buyer or not buyer.custom_photo_path:
        abort(404)
    
    photo_path = Path(buyer.custom_photo_path)
    if not photo_path.exists():
        abort(404)
    
    return send_file(photo_path)


@app.route('/api/surplus')
def api_surplus():
    """Получить список излишков"""
    surplus = db.get_surplus_goods()
    return jsonify({
        'surplus': [
            {
                'goods_uid': s.goods_uid,
                'scanned_code': s.scanned_code,
                'sticker_code': s.sticker_code if hasattr(s, 'sticker_code') else None,
                'decoded_scanned_code': s.decoded_scanned_code,
                'is_error_surplus': s.is_error_surplus,
                'cell': s.cell,
                'is_dbs': s.is_dbs,
                'created_at': s.created_at if hasattr(s, 'created_at') else None
            }
            for s in surplus
        ],
        'count': len(surplus)
    })


@app.route('/api/surplus', methods=['DELETE'])
def api_surplus_clear():
    """Очистить все излишки"""
    try:
        db.clear_surplus_goods()
        return jsonify({'success': True, 'message': 'Излишки очищены'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/surplus/<goods_uid>', methods=['DELETE'])
def api_surplus_delete_one(goods_uid: str):
    """Удалить один излишек"""
    try:
        if db.delete_surplus_item(goods_uid):
            return jsonify({'success': True, 'message': 'Излишек удалён'})
        else:
            return jsonify({'error': 'Излишек не найден'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delivered')
def api_delivered():
    """Получить историю выданных товаров"""
    limit = request.args.get('limit', 100, type=int)
    query = request.args.get('q', '').strip()
    
    if query:
        orders = db.search_delivered_goods(query)
    else:
        orders = db.get_delivered_goods(limit)
    
    # Добавляем URL картинок
    orders = [add_image_url_to_dict(o) for o in orders]

    return jsonify({
        'orders': orders,
        'count': len(orders)
    })


@app.route('/api/delivered/order/<goods_uid>')
def api_delivered_order(goods_uid: str):
    """Получить весь заказ по goods_uid одного товара"""
    orders = db.get_order_by_goods_uid(goods_uid)
    # Добавляем URL картинок
    orders = [add_image_url_to_dict(o) for o in orders]

    return jsonify({
        'orders': orders,
        'count': len(orders)
    })


@app.route('/api/buyer/<user_sid>/custom', methods=['POST'])
def api_buyer_custom_update(user_sid: str):
    """Обновить кастомные данные клиента (альтернативный эндпоинт)"""
    data = request.get_json()
    
    db.update_buyer_custom_data(
        user_sid,
        custom_name=data.get('custom_name'),
        custom_description=data.get('description')
    )
    
    return jsonify({'success': True})


@app.route('/api/cached_image/<vendor_code>')
def api_serve_cached_image(vendor_code: str):
    """
    Отдать кэшированное изображение, если оно есть локально.
    """
    num = request.args.get('num', 1, type=int)

    # Путь к файлу в кэше
    path = wb_api.get_cached_image_path(vendor_code, num)

    # Если файл есть и не пустой - отдаём
    if path.exists() and path.stat().st_size > 0:
        return send_file(path)

    # Если файла нет - возвращаем 404 (чтобы не парсить ссылки автоматически)
    abort(404)


@app.route('/api/image/cache/<vendor_code>', methods=['POST'])
def api_cache_image(vendor_code: str):
    """
    Принудительно скачать и сохранить изображение в кэш
    """
    size = request.args.get('size', 'small')
    num = request.args.get('num', 1, type=int)

    path, _ = wb_api.download_image_sync(vendor_code, num, size, force=True)
    if path and path.exists():
        # Возвращаем ссылку на локальный кэш с timestamp для сброса кэша браузера
        return jsonify({
            'success': True,
            'url': f"/api/cached_image/{vendor_code}?num={num}&t={int(time.time())}"
        })
    else:
        return jsonify({'success': False, 'error': 'Not found'}), 404


@app.route('/api/buyer/<user_sid>/cache-images', methods=['POST'])
def api_buyer_cache_images(user_sid: str):
    """
    Скачать изображения для всех товаров клиента (в фоне)
    """
    # Очистка старого прогресса (старше 5 минут)
    now = time.time()
    to_remove = [sid for sid, p in download_progress.items() if p.get('finished') and (now - p.get('finished_at', 0)) > 300]
    for sid in to_remove:
        download_progress.pop(sid, None)

    if user_sid in active_downloads:
        return jsonify({'success': False, 'message': 'Загрузка уже запущена', 'count': 0})

    # Получаем тип товаров для загрузки
    data = request.get_json(silent=True) or {}
    goods_type = data.get('type', 'all')  # all, ready, onway

    all_goods = db.get_all_goods_by_buyer(user_sid)

    # Фильтруем товары
    if goods_type == 'ready':
        goods_to_process = [g for g in all_goods if g.status == 'GOODS_READY']
    elif goods_type == 'onway':
        goods_to_process = [g for g in all_goods if g.is_on_way]
    else:
        goods_to_process = all_goods

    if not goods_to_process:
        return jsonify({'success': True, 'count': 0})

    # Блокируем сразу, чтобы избежать race condition
    active_downloads.add(user_sid)

    # Инициализируем прогресс
    download_progress[user_sid] = {
        'total': len(goods_to_process),
        'current': 0,
        'finished': False
    }

    def download_task():
        try:
            print(f"[BulkUpdate] Starting for {user_sid}, items: {len(goods_to_process)}")
            # Сортируем: сначала готовы к выдаче, потом в пути, потом остальные
            sorted_goods = sorted(goods_to_process, key=lambda g: (
                0 if g.status == 'GOODS_READY' else
                1 if g.is_on_way else
                2
            ))

            # Добавляем задержку чтобы не спамить запросами
            for i, g in enumerate(sorted_goods):
                # Обновляем прогресс
                if user_sid in download_progress:
                    download_progress[user_sid]['current'] = i

                if g.vendor_code:
                    try:
                        # Используем force=False, чтобы пропускать уже скачанные
                        # Но если файла нет - он скачается
                        path, downloaded = wb_api.download_image_sync(g.vendor_code, 1, 'small', force=False)

                        if downloaded:
                            print(f"[BulkUpdate] Downloaded {g.vendor_code} ({i+1}/{len(sorted_goods)})")
                            time.sleep(0.2)  # Баланс скорости и стабильности
                        else:
                            # Если не скачали - либо уже есть, либо ошибка
                            if path and path.exists():
                                # Уже есть в кэше
                                time.sleep(0.02)
                            else:
                                print(f"[BulkUpdate] Failed to download {g.vendor_code} ({i+1}/{len(sorted_goods)})")
                                time.sleep(0.2) # Пауза при ошибке
                    except Exception as e:
                        print(f"[BulkUpdate] Error processing {g.vendor_code}: {e}")
                        time.sleep(0.5)

            # Финальный прогресс
            if user_sid in download_progress:
                download_progress[user_sid]['current'] = len(sorted_goods)

            print(f"[BulkUpdate] Finished for {user_sid}")
        except Exception as e:
            print(f"[BulkUpdate] Fatal error for {user_sid}: {e}")
        finally:
            active_downloads.discard(user_sid)
            if user_sid in download_progress:
                download_progress[user_sid]['finished'] = True
                download_progress[user_sid]['finished_at'] = time.time()

    # Запускаем в отдельном потоке
    threading.Thread(target=download_task, daemon=True).start()

    return jsonify({'success': True, 'count': len(goods_to_process), 'message': 'Фоновая загрузка запущена'})


@app.route('/api/buyer/<user_sid>/download-progress')
def api_buyer_download_progress(user_sid: str):
    """Получить статус загрузки картинок"""
    if user_sid in download_progress:
        return jsonify(download_progress[user_sid])
    return jsonify({'total': 0, 'current': 0, 'finished': True})


@app.route('/api/images/check-status', methods=['POST'])
def api_check_images_status():
    """Массовая проверка наличия картинок в кэше"""
    data = request.get_json()
    codes = data.get('codes', [])

    result = {}
    for code in set(codes):
        str_code = str(code)
        # Проверяем наличие в кэше
        path = wb_api.get_cached_image_path(str_code, 1)
        if path.exists() and path.stat().st_size > 0:
            result[str_code] = f"/api/cached_image/{str_code}?num=1&t={int(path.stat().st_mtime)}"

    return jsonify(result)


@app.route('/api/qr/<encoded_code>')
def api_qr_code(encoded_code: str):
    """Сгенерировать QR-код с кэшированием браузером"""
    # Получаем размер из параметров (для превью меньше)
    size = request.args.get('size', 8, type=int)
    size = min(max(size, 4), 12)  # Ограничиваем 4-12
    
    png_data = qr_generator.generate(encoded_code, box_size=size)
    if not png_data:
        abort(500)
    
    from io import BytesIO
    response = send_file(
        BytesIO(png_data),
        mimetype='image/png',
        as_attachment=False
    )
    # Кэшируем на клиенте на 1 час
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


@app.route('/api/image/<vendor_code>')
def api_product_image(vendor_code: str):
    """Получить URL изображения товара (локальный кэш)"""
    size = request.args.get('size', 'small')
    num = request.args.get('num', 1, type=int)
    
    # Возвращаем ссылку на наш кэширующий эндпоинт
    url = f"/api/cached_image/{vendor_code}?size={size}&num={num}"
    return jsonify({'url': url})


@app.route('/api/image/find/<vendor_code>')
def api_find_product_image(vendor_code: str):
    """Найти рабочий URL изображения товара (пробует разные серверы)"""
    size = request.args.get('size', 'small')
    num = request.args.get('num', 1, type=int)
    
    url = wb_api.find_working_image_url_sync(vendor_code, num, size)
    if url:
        return jsonify({'url': url, 'found': True})
    else:
        # Если не нашли, возвращаем основной URL
        fallback_url = wb_api.get_image_url(vendor_code, num, size)
        return jsonify({'url': fallback_url, 'found': False})


@app.route('/api/vendor-codes')
def api_vendor_codes():
    """Получить все уникальные vendor_code для предзагрузки картинок"""
    codes = db.get_all_vendor_codes()
    return jsonify({
        'codes': codes,
        'count': len(codes)
    })


@app.route('/api/image/all/<vendor_code>')
def api_all_product_image_urls(vendor_code: str):
    """Получить все возможные URL изображений товара"""
    size = request.args.get('size', 'small')
    num = request.args.get('num', 1, type=int)
    
    urls = wb_api.get_all_possible_image_urls(vendor_code, num, size)
    primary_url = wb_api.get_image_url(vendor_code, num, size)
    
    return jsonify({
        'primary_url': primary_url,
        'all_urls': urls
    })


@app.route('/api/deliveries')
def api_deliveries():
    """Получить историю доставок"""
    limit = request.args.get('limit', 50, type=int)
    orders = db.get_recent_deliveries(limit)
    
    return jsonify({
        'orders': [
            {
                'order_id': o.order_id,
                'delivery_date': o.delivery_date,
                'items_count': o.items_count,
                'items': o.items
            }
            for o in orders
        ]
    })


@app.route('/api/voiceover/files')
def api_voiceover_files():
    """Получить список звуковых файлов по категориям"""
    metadata = load_metadata()
    
    categories = {
        'system': [],
        'woman': [],
        'cells': []
    }
    
    def get_display_name(rel_path, filename):
        return metadata.get(rel_path, {}).get('name', filename)

    # System sounds (root of sounds folder)
    if SOUNDS_DIR.exists():
        for f in SOUNDS_DIR.glob('*.mp3'):
            rel_path = f.name
            categories['system'].append({
                'filename': f.name,
                'path': str(f),
                'rel_path': rel_path,
                'display_name': get_display_name(rel_path, f.name),
                'category': 'system',
                'mtime': f.stat().st_mtime
            })
            
    # Woman sounds
    woman_dir = SOUNDS_DIR / 'woman'
    if woman_dir.exists():
        for f in woman_dir.glob('*.mp3'):
            rel_path = f"woman/{f.name}"
            categories['woman'].append({
                'filename': f.name,
                'path': str(f),
                'rel_path': rel_path,
                'display_name': get_display_name(rel_path, f.name),
                'category': 'woman',
                'mtime': f.stat().st_mtime
            })
            
    # Cells sounds
    cells_dir = woman_dir / 'cells'
    if cells_dir.exists():
        for f in cells_dir.glob('*.mp3'):
            rel_path = f"woman/cells/{f.name}"
            categories['cells'].append({
                'filename': f.name,
                'path': str(f),
                'rel_path': rel_path,
                'display_name': get_display_name(rel_path, f.name),
                'category': 'cells',
                'mtime': f.stat().st_mtime
            })
            
    # Sort by display name
    def natural_key(item):
        text = item['display_name']
        return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', text)]

    for cat in categories:
        if cat == 'cells':
            categories[cat].sort(key=natural_key)
        else:
            categories[cat].sort(key=lambda x: x['display_name'])
        
    return jsonify(categories)


@app.route('/api/voiceover/metadata', methods=['POST'])
def api_voiceover_update_metadata():
    """Обновить метаданные (название) файла"""
    data = request.get_json()
    rel_path = data.get('rel_path')
    display_name = data.get('display_name')
    
    if not rel_path or not display_name:
        return jsonify({'error': 'Missing fields'}), 400
        
    metadata = load_metadata()
    if rel_path not in metadata:
        metadata[rel_path] = {}
    
    metadata[rel_path]['name'] = display_name
    save_metadata(metadata)
    
    return jsonify({'success': True})


@app.route('/api/voiceover/play/<path:filename>')
def api_voiceover_play(filename):
    """Воспроизвести файл"""
    # filename is relative path from sounds dir
    file_path = SOUNDS_DIR / filename
    if not file_path.exists():
        abort(404)
    return send_file(file_path)


@app.route('/api/voiceover/generate', methods=['POST'])
def api_voiceover_generate():
    """Генерация TTS (превью)"""
    data = request.get_json()
    text = data.get('text', '')
    voice = data.get('voice', 'ru-RU-DmitryNeural')
    rate = data.get('rate', '+5%')
    pitch = data.get('pitch', '-10Hz')
    volume = float(data.get('volume', 5))
    
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    output_path = temp_dir / f"preview_{int(time.time())}.mp3"
    
    success, error = tts_manager.generate_tts(
        text=text,
        output_path=output_path,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume_db=volume
    )
    
    if not success:
        return jsonify({'error': error}), 500
        
    return send_file(output_path, mimetype='audio/mpeg')


@app.route('/api/voiceover/save', methods=['POST'])
def api_voiceover_save():
    """Сохранить TTS в файл"""
    data = request.get_json()
    rel_path = data.get('rel_path')
    text = data.get('text', '')
    voice = data.get('voice', 'ru-RU-DmitryNeural')
    rate = data.get('rate', '+5%')
    pitch = data.get('pitch', '-10Hz')
    volume = float(data.get('volume', 5))
    
    if not rel_path:
        return jsonify({'error': 'No file path provided'}), 400
        
    output_path = SOUNDS_DIR / rel_path
    if not output_path.parent.exists():
        return jsonify({'error': 'Directory does not exist'}), 404
        
    success, error = tts_manager.generate_tts(
        text=text,
        output_path=output_path,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume_db=volume
    )
    
    if not success:
        return jsonify({'error': error}), 500
        
    return jsonify({'success': True, 'message': 'Файл успешно обновлен. Не забудьте применить патч!'})


@app.route('/api/voiceover/upload', methods=['POST'])
def api_voiceover_upload():
    """Загрузить MP3 файл"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    rel_path = request.form.get('rel_path')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if not rel_path:
        return jsonify({'error': 'No target path provided'}), 400
        
    target_path = SOUNDS_DIR / rel_path
    file.save(target_path)
    
    return jsonify({'success': True, 'message': 'Файл заменен. Не забудьте применить патч!'})


@app.route('/api/voiceover/patch', methods=['POST'])
def api_voiceover_patch():
    """Применить патч (копирование файлов с правами администратора)"""
    try:
        # Проверяем существование исходной папки
        if not SOUNDS_DIR.exists():
            return jsonify({'error': 'Исходная папка sounds не найдена'}), 404

        # Формируем PowerShell команду для копирования с повышением прав
        # Используем Copy-Item с флагом -Force и -Recurse
        # Важно: экранирование кавычек
        
        src_path = str(SOUNDS_DIR).rstrip('\\')
        dst_path = str(TARGET_SOUNDS_DIR).rstrip('\\')
        
        # Команда PowerShell, которая будет запущена с правами админа
        ps_command = f"Copy-Item -Path '{src_path}\\*' -Destination '{dst_path}' -Recurse -Force"
        
        # Оборачиваем в Start-Process -Verb RunAs для запроса UAC
        full_command = [
            "powershell",
            "-Command",
            f"Start-Process powershell -ArgumentList \"-NoProfile -Command {ps_command}\" -Verb RunAs -WindowStyle Hidden -Wait"
        ]
        
        # Запускаем
        process = subprocess.run(full_command, capture_output=True, text=True)
        
        if process.returncode == 0:
            return jsonify({'success': True, 'message': 'Запрос на обновление отправлен. Подтвердите действие в окне UAC (если появилось).'})
        else:
            return jsonify({'error': f'Ошибка запуска патчера: {process.stderr}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============== BOT MANAGER ==============

@app.route('/bot')
def bot_manager_page():
    return render_template('bot_manager.html')

@app.route('/api/bot/status')
def api_bot_status():
    is_running = bot_manager.is_running()
    return jsonify({'running': is_running})

@app.route('/api/bot/start', methods=['POST'])
def api_bot_start():
    success, message = bot_manager.start()
    return jsonify({'success': success, 'message': message})

@app.route('/api/bot/stop', methods=['POST'])
def api_bot_stop():
    success, message = bot_manager.stop()
    return jsonify({'success': success, 'message': message})

@app.route('/api/bot/config', methods=['GET', 'POST'])
def api_bot_config():
    if request.method == 'POST':
        new_config = request.json
        success = bot_manager.save_config(new_config)
        return jsonify({'success': success})
    else:
        config = bot_manager.get_config()
        return jsonify(config)

@app.route('/api/bot/clear_photos', methods=['POST'])
def api_bot_clear_photos():
    count = bot_manager.clear_photos()
    return jsonify({'success': True, 'count': count})


@app.route('/api/utils/select-folder', methods=['POST'])
def api_select_folder():
    """Открыть диалог выбора папки"""
    try:
        # Принудительно используем python.exe вместо pythonw.exe для доступа к stdout
        python_exe = sys.executable.replace('pythonw.exe', 'python.exe')

        cmd = [
            python_exe,
            '-c',
            "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1); print(filedialog.askdirectory());"
        ]

        # Для Windows скрываем окно консоли
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            creationflags=creationflags
        )

        raw_output = result.stdout
        path = None

        # Пытаемся декодировать разными кодировками
        encodings = ['utf-8', 'cp1251', 'cp866']
        if os.name == 'nt':
            encodings.insert(0, 'mbcs')  # ANSI code page on Windows

        for enc in encodings:
            try:
                decoded = raw_output.decode(enc).strip()
                if decoded:
                    path = decoded
                    break
            except Exception:
                continue

        if path:
            return jsonify({'success': True, 'path': path})
        else:
            return jsonify({'success': False, 'message': 'Выбор отменен'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ============== MAIN ==============

def stop_services():
    """Stop all background services."""
    print("[Main] Stopping services...")
    try:
        bot_manager.stop()
    except Exception as e:
        print(f"[Main] Error stopping bot: {e}")


if __name__ == '__main__':
    # Запрос прав администратора (Windows)
    if os.name == 'nt':
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False

        if not is_admin:
            # Re-run the program with admin rights
            # "runas" - это глагол ShellExecute, который запрашивает элевацию
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, subprocess.list2cmdline(sys.argv), None, 1
            )
            sys.exit()

    print(f"""
╔════════════════════════════════════════════╗
║         WB Manager v1.0                    ║
║   Интерфейс управления ПВЗ Wildberries     ║
╠════════════════════════════════════════════╣
║   Открой в браузере:                       ║
║   http://{APP_HOST}:{APP_PORT}                       ║
╚════════════════════════════════════════════╝
    """)
    is_primary_process = (not DEBUG_MODE) or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    if is_primary_process:
        auto_start_bot_if_needed()

    tray_icon = None
    if is_primary_process:
        try:
            tray_icon = TrayIconManager(APP_HOST, APP_PORT, on_exit=stop_services)
            tray_icon.start()
        except Exception as exc:
            tray_icon = None
            print(f"[Tray] Не удалось запустить значок: {exc}")

    try:
        app.run(
            host=APP_HOST,
            port=APP_PORT,
            debug=DEBUG_MODE,
            threaded=True
        )
    finally:
        if tray_icon:
            tray_icon.stop()
        if is_primary_process:
            stop_services()
