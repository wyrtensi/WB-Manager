# WB Assist App — Technical Field Guide

> Этот документ написан для разработчиков и AI-агентов, которым нужно быстро погрузиться в архитектуру проекта, понять, где находятся ключевые точки расширения, и безопасно вносить изменения.

## 1. Система в двух словах

| Компонент | Назначение | Входные данные | Выходные данные |
|-----------|------------|----------------|-----------------|
| **WB Manager** (`wb_manager/`) | Flask-приложение, рендерит Jinja UI, предоставляет REST/JSON API | SQLite `wb_point_db.sqlite`, кеш изображений, пользовательские данные | HTML, JSON, управление ботом, TTS медиа |
| **Telegram Bot** (`wb_manager/telegram_bot/`) | Мониторинг поставок/приёмки, уведомления, приём фото | Wildberries portal (`pvz-lk.wb.ru`), пользовательские сообщения | Уведомления, сохранённые фото, `bot_state.json` |

## 2. Дерево проекта (с фокусом на активных директориях)

```
wb_manager/
├── README.md                # Общее описание и quick start
├── agents.md                # (этот файл)
├── main.py                  # Точка входа Flask
├── config.py                # Пути, статусы, настройки
├── requirements.txt         # Общие зависимости (UI + бот)
├── api/
│   └── wb_api.py            # Доставка изображений WB
├── database/
│   └── database_manager.py  # Singleton для SQLite
├── models/
│   └── data_models.py       # Dataclass-модели WB
├── static/
│   ├── js/app.js            # Очередь картинок, поиск, UI логика
│   └── css/styles.css       # Тёмная тема, компоненты
├── templates/               # Jinja-шаблоны (index, goods, buyers, bot_manager…)
├── utils/
│   ├── bot_manager.py       # Управление процессом бота
│   ├── qr_generator.py      # Кешируемые QR
│   └── tts_manager.py       # Edge TTS + FFmpeg
├── telegram_bot/
│   ├── wb_telegram_bot.py   # Асинхронный бот (Playwright + PTB)
│   ├── bot_config.json      # Конфигурация (редактируется UI)
│   ├── bot_state.json       # Текущее состояние авторизации
│   ├── cookies/localstorage/user_agent.txt
│   └── *.json               # Буферные данные (deliveries, notified…)
└── sounds/, voiceover/, custom_data/, cache/, ...
```

## 3. Потоки управления

### 3.1 Веб-интерфейс

1. `main.py` регистрирует Flask-приложение, подключает `db = DatabaseManager()` и вспомогательные менеджеры (бот, TTS).
2. Шаблоны (Jinja) используют данные, подготовленные Python-кодом (например, `goods.html` получает данные через AJAX `fetch('/api/goods/pickup')`).
3. Frontend-скрипт `static/js/app.js` отвечает за:
	- Очередь загрузки изображений и localStorage-кеширование.
	- Поиск, фильтры, пагинацию, бесконечный скролл.
	- Вызовы REST-endpoints (см. раздел 7).
4. Страница `bot_manager.html` взаимодействует с REST-ручками `/api/bot/*` и редактирует `bot_config.json`.

### 3.2 Telegram Bot

1. Скрипт `wb_telegram_bot.py` запускает два процесса (Multiprocessing):
	- **Bot Process**: Основной цикл Telegram (`Application.run_polling`). Отвечает на команды, отправляет уведомления, сохраняет фото.
	- **Monitor Process**: Фоновый процесс с Playwright. Периодически (раз в 3 мин) проверяет `upcoming-deliveries` и `acceptance-statistics`, пишет данные в JSON и шлёт события в Bot Process через очередь.
2. Стейт-машина авторизации (`AUTH_STATE`) управляется Monitor Process, который запрашивает код через очередь команд.
3. При найденной поставке/приёмке Monitor Process отправляет событие `broadcast` в Bot Process, который вызывает `send_notification_to_users()`.
4. Фото от разрешённых пользователей сохраняются Bot Process в `photo_save_path` (из конфига).
5. Статус «Авторизован/Нет авторизации» синхронизируется через `save_bot_state(bool)` и события очереди.

## 4. Конфигурация и секреты

| Файл | Ответственность | Изменяется вручную? |
|------|-----------------|---------------------|
| `wb_manager/config.py` | Пути к БД, каталогам, константы статусов, порты | Да (при переносе окружения) |
| `wb_manager/telegram_bot/bot_config.json` | Токен Telegram, список пользователей, директория фото, текст auth message | Через UI или руками |
| `wb_manager/telegram_bot/bot_state.json` | Флаг `is_authorized`, timestamp | Нет (поддерживается ботом) |
| `wb_manager/custom_data/custom_buyers.json` | Кастомные фото/имена клиентов | Да, через UI или вручную |

> ⚠️ При добавлении новых настроек для бота убедитесь, что их читает и UI (страница `bot_manager.html`), и сам бот (`load_config()` в `wb_telegram_bot.py`).

## 5. Данные и базы

- Основная БД: `wb_point_db.sqlite` (устанавливается приложением WB Point). Путь описан в `config.DATABASE_PATH`.
- `DatabaseManager` использует `sqlite3` + контекстный менеджер, кеширует подключение, подмешивает пользовательские данные (custom photos) при выдаче клиентов.
- Дополнительные JSON-файлы в `telegram_bot/` содержат кеш состояний (deliveries, notified, acceptance_notified). Они могут быть очищены без потери критических данных.

## 6. API и endpoints

| Endpoint | Метод | Описание | Файл |
|----------|-------|----------|------|
| `/api/stats` | GET | Общая статистика по товарам | `main.py` |
| `/api/goods/pickup` | GET | Список товаров на ПВЗ (limit/offset/status) | `main.py` |
| `/api/goods/on-way` | GET | Товары в пути | `main.py` |
| `/api/buyers` | GET | Клиенты (фильтры: `with-cell`, `missing-photo`, `all`) | `main.py` |
| `/api/buyer/<sid>` | GET | Конкретный клиент + товары | `main.py` |
| `/api/search` | GET | Глобальный поиск по ШК/телефону/ФИО | `main.py` |
| `/api/qr/<code>` | GET | Возвращает PNG QR (через `qr_generator`) | `main.py` |
| `/api/bot/status` | GET | Состояние процесса бота (через `BotManager.is_running`) | `main.py` |
| `/api/bot/config` | GET/POST | Читает/сохраняет `bot_config.json` | `main.py` + `BotManager` |
| `/api/bot/start|stop|restart` | POST | Управление процессом бота | `main.py` + `BotManager` |
| `/api/bot/clear_photos` | POST | Удаление файлов из папки фото | `BotManager.clear_photos` |

## 7. Фронтенд (app.js)

Ключевые блоки:

1. **API helper** — централизует `fetch`, добавляя обработку ошибок.
2. **Toast** — lightweight уведомления.
3. **Image pipeline**:
	- `workingImageUrls` (localStorage) + `failedImageUrls` (session Set).
	- Очереди `priorityImageQueue`/`backgroundImageQueue` и `processImageQueue()` с лимитом параллелизма, чтобы не перегружать сеть.
	- Функции `queueImage`, `loadImageImmediately`, `refreshModalImage`.
4. **Списки** — функции `loadMoreBuyers`, `loadGoods`, `loadSurplus` используют одинаковый паттерн: показывают loader, тянут JSON, рендерят карточки.
5. **Bot manager JS** — в `bot_manager.html` находится отдельный `<script>` c методами `updateStatus`, `loadConfig`, `saveConfig`, `toggleAdmin`, `toggleNotify` и т.д.

## 8. Telegram Bot глубже

### Архитектура `wb_telegram_bot.py` (Multiprocessing)

Для исключения блокировок основного цикла бота (asyncio) тяжелыми операциями Playwright, приложение разделено на два процесса:

1. **Main Process (Bot)**:
    - Запускает `MonitorProcess`.
    - Инициализирует `Application` (python-telegram-bot).
    - Слушает очередь событий (`event_queue`) от монитора: запросы на рассылку, запросы кода авторизации, статус авторизации.
    - Отправляет команды (`cmd_queue`) монитору: начать авторизацию, отправить код.

2. **Monitor Process**:
    - Запускает собственный asyncio loop.
    - Выполняет `check_and_notify_loop()` (Playwright check every 3 mins).
    - Выполняет `perform_authorization()` (Playwright login flow).
    - Пишет результаты в shared JSON-файлы (`deliveries.json`, `acceptances.json`).

### Основные блоки

- **Config loading**: Оба процесса загружают конфиг из `bot_config.json`.
- **State persistence**: `bot_state.json` обновляется Monitor Process, читается UI.
- **Playwright**: `get_status_playwright()` работает в Monitor Process, поднимает Chromium (headless).
- **Authorization workflow**:
    1. Пользователь шлет телефон → Bot Process кидает `auth_start` в очередь.
    2. Monitor Process начинает авторизацию, доходит до кода, кидает `request_code` в очередь.
    3. Bot Process просит код у юзера. Юзер шлет код → Bot Process кидает `auth_code`.
    4. Monitor Process вводит код, сохраняет сессию.
- **Notifications**: Monitor Process кидает `broadcast` событие, Bot Process вызывает `send_notification_to_users()`.
- **Photo handling**: Обрабатывается полностью в Bot Process (так как Playwright не нужен).

### Файлы данных бота

| Файл | Содержимое |
|------|------------|
| `deliveries.json` | Последние поставки (кешируется между циклами) |
| `notified.json` | Уникальные ключи поставок, по которым уже отправлено уведомление |
| `acceptances.json` / `acceptance_notified.json` | Аналогично для приёмки |
| `sent_messages.json` | ID сообщений, отправленных ботом (для удаления при рестарте) |
| `user_chat_ids.json` | Username → chat_id (чтобы бот мог писать первым) |

## 9. Звук и озвучка

- Каталог `sounds/` содержит целевые аудио.
- `voiceover.html` + JS позволяют прослушивать и генерировать TTS фразы, используя Edge TTS через `tts_manager.py`.
- FFmpeg обязателен: `TTSManager.find_ffmpeg()` ищет бинарь в фиксированных путях. При доработке добавляйте новые пути или настройку в `config.py`.

## 10. Типовые задачи и рецепты

### Добавить новый REST endpoint
1. Открой `wb_manager/main.py` и добавь `@app.route('/api/...')`.
2. Получи данные через `db` или другие менеджеры.
3. Верни `jsonify` (не забудь `JSON_AS_ASCII=False` уже настроен).
4. Если endpoint будет дергать фронтенд, зафиксируй его в `static/js/app.js` (API helper) и обнови UI.

### Расширить Telegram-бота
1. Добавь конфигурацию в `bot_config.json` и обработку в `load_config()`.
2. Отрази параметр в странице `bot_manager.html` (input → `saveConfig`).
3. Используй существующие helpers (например, `send_notification_to_users`).
4. Если нужно хранить новые данные, положи JSON рядом и убедись, что боту не нужен эксклюзивный доступ (используй `Path.exists()` проверки).

### Добавить поле к клиенту
1. Обнови `models/data_models.py` (dataclass `Buyer`).
2. Пробрось поле в `database_manager.py` (select + map → Buyer).
3. Отобрази его в нужном шаблоне (например, `buyer_profile.html`).

## 11. Практические советы

- **Не удаляйте** `bot_state.json`, `cookies.json`, `localstorage.json`, если не хотите сбрасывать авторизацию.
- **Хранилище изображений**: `cache/images` можно очищать, но браузерный localStorage всё равно содержит рабочие URL. Для полного сброса очистите localStorage в DevTools.
- **Дубликаты папок `wb_manager - Copy`** — это резервные копии, в рабочую структуру они не подгружаются. Любые изменения делайте в `wb_manager/`.
- **psutil** и `pythonw` используются для фонового запуска бота без консоли (см. `BotManager.start`).

## 12. Контрольный список перед PR/коммитом

1. `README.md` и `agents.md` отражают последние архитектурные изменения.
2. Новые зависимости добавлены в соответствующий `requirements.txt`.
3. При изменении бота — протестируйте авторизацию и отправку сообщений на тестовом аккаунте.
4. UI изменения проверяйте в последнем Chrome/Edge (есть кастомные CSS-переменные и темы).

---

Дополнительные вопросы и идеи по развитию лучше фиксировать прямо в README (раздел «Планы и улучшения»), чтобы команда понимала приоритеты.
