# -*- coding: utf-8 -*-
"""
Модуль для работы с API Wildberries
Получение изображений товаров по vendor_code (артикулу)
С множественными fallback-источниками
"""
import requests
import concurrent.futures
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import logging

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import IMAGE_CACHE_DIR

# Настройка логгера
logger = logging.getLogger(__name__)

class WildberriesAPI:
    """Клиент для получения изображений товаров Wildberries"""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # Базовые URL для изображений WB
    BASKET_HOSTS = [f"basket-{i:02d}.wbbasket.ru" for i in range(1, 33)]
    
    def __init__(self):
        self.cache_dir = IMAGE_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._failed_images = {}  # Кэш неудачных попыток

        # Настройка сессии с пулом соединений для переиспользования TCP
        self.session = requests.Session()
        # Увеличиваем пул, чтобы хватило на check_executor (32 потока)
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=50,
            pool_maxsize=50,
            max_retries=1
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update(self.HEADERS)

        # Executor for background downloads
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="WB_Image_Download")
        # Shared executor for checking URLs
        self.check_executor = concurrent.futures.ThreadPoolExecutor(max_workers=32, thread_name_prefix="WB_URL_Check")
    
    @staticmethod
    def get_basket_number(vendor_code: str) -> int:
        """
        Определяет номер basket-сервера по артикулу
        Обновлённый алгоритм WB 2024-2025
        """
        try:
            nm_id = int(vendor_code)
        except (ValueError, TypeError):
            return 1
        
        # Обновлённые диапазоны (WB периодически их меняет) - 2025
        if nm_id < 14400000:
            return 1
        elif nm_id < 28800000:
            return 2
        elif nm_id < 43200000:
            return 3
        elif nm_id < 72000000:
            return 4
        elif nm_id < 100800000:
            return 5
        elif nm_id < 106200000:
            return 6
        elif nm_id < 111600000:
            return 7
        elif nm_id < 117000000:
            return 8
        elif nm_id < 131400000:
            return 9
        elif nm_id < 160200000:
            return 10
        elif nm_id < 165600000:
            return 11
        elif nm_id < 185400000:
            return 12
        elif nm_id < 214200000:
            return 13
        elif nm_id < 243000000:
            return 14
        elif nm_id < 280800000:
            return 15
        elif nm_id < 318600000:
            return 16
        elif nm_id < 360000000:
            return 17
        elif nm_id < 405000000:
            return 18
        elif nm_id < 450000000:
            return 19
        elif nm_id < 495000000:
            return 20
        elif nm_id < 540000000:
            return 21
        elif nm_id < 585000000:
            return 22
        elif nm_id < 630000000:
            return 23
        elif nm_id < 675000000:
            return 24
        elif nm_id < 720000000:
            return 25
        elif nm_id < 765000000:
            return 26
        elif nm_id < 810000000:
            return 27
        elif nm_id < 855000000:
            return 28
        elif nm_id < 900000000:
            return 29
        elif nm_id < 945000000:
            return 30
        else:
            return 31
    
    @staticmethod
    def get_vol_part(vendor_code: str) -> tuple:
        """Получить vol и part из артикула"""
        try:
            nm_id = int(vendor_code)
            vol = nm_id // 100000
            part = nm_id // 1000
            return vol, part
        except (ValueError, TypeError):
            return 0, 0
    
    def get_image_url(self, vendor_code: str, image_num: int = 1, 
                       size: str = "big") -> str:
        """
        Сформировать URL изображения товара
        
        Args:
            vendor_code: Артикул товара
            image_num: Номер изображения (1-10)
            size: Размер - "big" (516x688), "small" (246x328), "thumb" (100x100)
        
        Returns:
            URL изображения
        """
        basket = self.get_basket_number(vendor_code)
        vol, part = self.get_vol_part(vendor_code)
        
        basket_str = f"{basket:02d}"
        
        size_paths = {
            "big": "c516x688",
            "small": "c246x328",
            "thumb": "c100x100"
        }
        size_path = size_paths.get(size, "c516x688")
        
        return (
            f"https://basket-{basket_str}.wbbasket.ru/"
            f"vol{vol}/part{part}/{vendor_code}/images/{size_path}/{image_num}.webp"
        )
    
    def get_all_image_urls(self, vendor_code: str, pics_count: int = 1,
                           size: str = "small") -> List[str]:
        """Получить URL всех изображений товара"""
        return [
            self.get_image_url(vendor_code, i, size) 
            for i in range(1, min(pics_count + 1, 11))
        ]
    
    def get_cached_image_path(self, vendor_code: str, image_num: int = 1) -> Path:
        """Получить путь к кэшированному изображению"""
        return self.cache_dir / f"{vendor_code}_{image_num}.webp"
    
    def download_image_sync(self, vendor_code: str, image_num: int = 1,
                             size: str = "small", force: bool = False) -> Tuple[Optional[Path], bool]:
        """
        Синхронно скачать и закэшировать изображение товара
        
        Returns:
            (Path, bool) - Путь к файлу (или None), и флаг "был ли скачан" (True) или взят из кэша (False)
        """
        cache_path = self.get_cached_image_path(vendor_code, image_num)
        
        # Проверяем кэш
        if not force and cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path, False
        
        # Ищем рабочий URL (с использованием User-Agent и перебором серверов)
        url = self.find_working_image_url_sync(vendor_code, image_num, size)
        
        if not url:
            # Fallback to calculated URL if check failed
            url = self.get_image_url(vendor_code, image_num, size)

        try:
            # Используем сессию и уменьшенный таймаут (5с вместо 15с)
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                cache_path.write_bytes(response.content)
                return cache_path, True
            else:
                if response.status_code != 404:
                    logger.warning(f"Ошибка загрузки {vendor_code} (Status {response.status_code}): {url}")
        except Exception as e:
            # Логируем ошибку соединения короче
            logger.error(f"Исключение при загрузке {vendor_code}: {str(e).split('Caused by')[0]}")
        
        return None, False
    
    def queue_image_download(self, vendor_code: str, image_num: int = 1, size: str = "small"):
        """
        Поставить задачу на загрузку изображения в фоне.
        Отключено по требованию (убрано автоматическое скачивание).
        """
        pass

    def prefetch_images(self, vendor_codes: List[str],
                               size: str = "small") -> Dict[str, Optional[Path]]:
        """
        Предзагрузка изображений для списка артикулов (синхронно, с использованием пула)
        
        Returns:
            Словарь {vendor_code: path или None}
        """
        results = {}
        futures = {}
        
        # Запускаем задачи
        for vc in vendor_codes:
            futures[vc] = self.executor.submit(self.download_image_sync, vc, 1, size)

        # Собираем результаты
        for vc, future in futures.items():
            try:
                path, _ = future.result()
                results[vc] = path
            except Exception:
                results[vc] = None

        return results
    
    def clear_cache(self):
        """Очистить кэш изображений"""
        for file in self.cache_dir.glob("*.webp"):
            try:
                file.unlink()
            except OSError:
                pass
    
    def get_all_possible_image_urls(self, vendor_code: str, image_num: int = 1,
                                     size: str = "small") -> List[str]:
        """
        Получить все возможные URL для изображения (разные basket серверы)
        
        Returns:
            Список URL для проверки
        """
        try:
            vol = int(vendor_code) // 100000
            part = int(vendor_code) // 1000
        except (ValueError, TypeError):
            return []
        
        size_paths = {
            "big": "c516x688",
            "small": "c246x328",
            "thumb": "c100x100"
        }
        size_suffix = size_paths.get(size, "c246x328")
        urls = []
        
        # Пробуем все известные basket серверы
        for basket_num in range(1, 33):
            basket_host = f"basket-{basket_num:02d}.wbbasket.ru"
            url = f"https://{basket_host}/vol{vol}/part{part}/{vendor_code}/images/{size_suffix}/{image_num}.webp"
            urls.append(url)
        
        return urls
    
    def find_working_image_url_sync(self, vendor_code: str, image_num: int = 1,
                                     size: str = "small") -> Optional[str]:
        """
        Найти рабочий URL изображения, проверяя разные серверы
        
        Returns:
            Рабочий URL или None
        """
        # Сначала пробуем основной URL
        primary_url = self.get_image_url(vendor_code, image_num, size)
        
        try:
            # Используем сессию
            response = self.session.head(primary_url, timeout=2, allow_redirects=True)
            if response.status_code == 200:
                return primary_url
        except Exception:
            pass
        
        # Если основной не работает, пробуем другие серверы параллельно
        all_urls = self.get_all_possible_image_urls(vendor_code, image_num, size)
        urls_to_check = [url for url in all_urls if url != primary_url]
        
        def check_url(url):
            try:
                # Используем сессию
                response = self.session.head(url, timeout=2, allow_redirects=True)
                if response.status_code == 200:
                    return url
            except Exception:
                pass
            return None
        
        # Проверяем параллельно (максимум 10 потоков)
        try:
            # Используем общий пул
            futures = {self.check_executor.submit(check_url, url): url for url in urls_to_check}
            try:
                for future in concurrent.futures.as_completed(futures, timeout=5):
                    try:
                        result = future.result(timeout=1)
                        if result:
                            # Отменяем остальные, чтобы не грузить пул
                            for f in futures:
                                f.cancel()
                            return result
                    except Exception:
                        continue
            except concurrent.futures.TimeoutError:
                pass
            finally:
                # В любом случае стараемся отменить хвосты
                for f in futures:
                    f.cancel()
        except Exception:
            pass
        
        return None


# Глобальный экземпляр API клиента
wb_api = WildberriesAPI()
