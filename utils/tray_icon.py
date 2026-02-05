"""System tray utilities for WB Manager."""
from __future__ import annotations

import os
import threading
import webbrowser
from typing import Optional, Any, Callable

_IMPORT_ERROR: Optional[str] = None

try:  # Optional dependency handled higher in the stack
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover - handled at runtime
    pystray = None  # type: ignore
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore
    _IMPORT_ERROR = str(exc)

PRIMARY_COLOR = (203, 17, 171)
DARK_COLOR = (139, 10, 117)
HIGHLIGHT_COLOR = (255, 255, 255, 55)


class TrayIconManager:
    """Create and manage the WB Manager system-tray icon."""

    def __init__(self, host: str, port: int, title: str = "WB Manager", on_exit: Optional[Callable[[], None]] = None) -> None:
        self.host = host
        self.port = port
        self.title = title
        self.on_exit = on_exit
        self._icon: Optional[Any] = None
        self._lock = threading.RLock()
        self._available = pystray is not None and Image is not None
        self._unavailable_reason = _IMPORT_ERROR or 'pystray или Pillow не установлены'

    @property
    def is_available(self) -> bool:
        return self._available

    def start(self) -> None:
        if not self.is_available:
            print(f"[Tray] Значок недоступен: {self._unavailable_reason}")
            return
        with self._lock:
            if self._icon is not None:
                return
            image = self._create_icon_image()
            menu = pystray.Menu(
                pystray.MenuItem('Открыть панель', self._open_ui, default=True),
                pystray.MenuItem('Выход', self._exit_app)
            )
            self._icon = pystray.Icon("wb_manager", image, self.title, menu)
            self._icon.run_detached()
            print("[Tray] Значок запущен в системном трее")

    def stop(self) -> None:
        with self._lock:
            if self._icon is None:
                return
            self._icon.stop()
            self._icon = None
            print("[Tray] Значок в трее остановлен")

    def _open_ui(self, icon: Any, item: Any) -> None:  # pragma: no cover - UI side effect
        webbrowser.open(f"http://{self.host}:{self.port}")

    def _exit_app(self, icon: Any, item: Any) -> None:  # pragma: no cover - UI side effect
        self.stop()
        if self.on_exit:
            self.on_exit()
        os._exit(0)

    def _create_icon_image(self, size: int = 128) -> Any:
        assert Image is not None and ImageDraw is not None
        base = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        gradient = Image.new('RGBA', (size, size))
        draw = ImageDraw.Draw(gradient)
        for y in range(size):
            ratio = y / max(size - 1, 1)
            color = tuple(
                int(PRIMARY_COLOR[i] * (1 - ratio) + DARK_COLOR[i] * ratio)
                for i in range(3)
            ) + (255,)
            draw.line([(0, y), (size, y)], fill=color, width=1)

        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, size - 1, size - 1),
            radius=size // 5,
            fill=255
        )
        base.paste(gradient, (0, 0), mask)

        overlay = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.ellipse(
            (-size * 0.3, -size * 0.2, size * 0.9, size * 0.8),
            fill=HIGHLIGHT_COLOR
        )
        base = Image.alpha_composite(base, overlay)

        font = self._load_font(size)
        text = "WB"
        text_draw = ImageDraw.Draw(base)
        tw, th = self._measure_text(text_draw, text, font)
        position = ((size - tw) / 2, (size - th) / 2)
        text_draw.text((position[0], position[1] + 1), text, font=font, fill=(255, 255, 255, 180))
        text_draw.text(position, text, font=font, fill=(255, 255, 255, 255))
        return base

    def _load_font(self, size: int) -> Any:
        assert ImageFont is not None
        preferred_fonts = [
            ('arialbd.ttf', size // 2),
            ('arial.ttf', size // 2),
            ('segoeuib.ttf', size // 2)
        ]
        for font_name, font_size in preferred_fonts:
            try:
                return ImageFont.truetype(font_name, font_size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _measure_text(self, draw: Any, text: str, font: Any) -> tuple[float, float]:
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            try:
                return font.getsize(text)
            except Exception:
                # Fallback to approximate width/height
                return len(text) * font.size * 0.6, font.size


__all__ = ["TrayIconManager"]
