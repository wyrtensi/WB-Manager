# -*- coding: utf-8 -*-
"""
Генератор QR-кодов для encoded_scanned_code
С кэшированием для производительности
"""
import io
import base64
import hashlib
from pathlib import Path
from typing import Optional, Union

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    from PIL import Image  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class QRGenerator:
    """Генератор QR-кодов для штрихкодов товаров с кэшированием"""
    
    def __init__(self, box_size: int = 10, border: int = 2):
        """
        Args:
            box_size: Размер одного "пикселя" QR-кода
            border: Ширина белой рамки вокруг QR-кода
        """
        self.box_size = box_size
        self.border = border
        self._cache = {}  # In-memory кэш
        self._max_cache_size = 500  # Максимум записей в кэше
    
    def _get_cache_key(self, data: str, box_size: int, border: int) -> str:
        """Генерация ключа кэша"""
        return hashlib.md5(f"{data}:{box_size}:{border}".encode()).hexdigest()[:16]
    
    def generate(self, data: str, 
                 box_size: int = None,
                 border: int = None) -> Optional[bytes]:
        """
        Генерация QR-кода в формате PNG (байты) с кэшированием
        """
        if not HAS_QRCODE or not data:
            return None
        
        box_size = box_size or self.box_size
        border = border or self.border
        
        # Проверяем кэш
        cache_key = self._get_cache_key(data, box_size, border)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,  # Быстрее генерируется
                box_size=box_size,
                border=border
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=False)  # Без оптимизации - быстрее
            result = buffer.getvalue()
            
            # Сохраняем в кэш
            if len(self._cache) >= self._max_cache_size:
                # Очищаем половину кэша
                keys = list(self._cache.keys())[:len(self._cache) // 2]
                for k in keys:
                    del self._cache[k]
            
            self._cache[cache_key] = result
            return result
        
        except Exception as e:
            print(f"Ошибка генерации QR-кода: {e}")
            return None
    
    def generate_base64(self, data: str, 
                        box_size: int = None,
                        border: int = None) -> Optional[str]:
        """
        Генерация QR-кода в формате Base64 для встраивания в HTML
        
        Returns:
            Data URL строка для использования в <img src="...">
        """
        png_bytes = self.generate(data, box_size, border)
        if png_bytes:
            b64 = base64.b64encode(png_bytes).decode('utf-8')
            return f"data:image/png;base64,{b64}"
        return None
    
    def generate_svg(self, data: str) -> Optional[str]:
        """
        Генерация QR-кода в формате SVG (более лёгкий)
        
        Returns:
            SVG строка
        """
        if not HAS_QRCODE:
            return None
        
        if not data:
            return None
        
        try:
            import qrcode.image.svg
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            factory = qrcode.image.svg.SvgImage
            img = qr.make_image(image_factory=factory)
            
            buffer = io.BytesIO()
            img.save(buffer)
            return buffer.getvalue().decode('utf-8')
        
        except Exception as e:
            print(f"Ошибка генерации SVG QR-кода: {e}")
            return None
    
    def save_to_file(self, data: str, filepath: Union[str, Path],
                      box_size: int = None) -> bool:
        """
        Сохранить QR-код в файл
        
        Args:
            data: Данные для кодирования
            filepath: Путь для сохранения
            box_size: Размер "пикселя"
        
        Returns:
            True при успехе, False при ошибке
        """
        png_bytes = self.generate(data, box_size)
        if png_bytes:
            try:
                Path(filepath).write_bytes(png_bytes)
                return True
            except IOError as e:
                print(f"Ошибка сохранения QR-кода: {e}")
        return False


# Глобальный экземпляр генератора
qr_generator = QRGenerator()
