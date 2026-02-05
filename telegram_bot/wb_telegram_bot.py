import asyncio
import json
import os
import random
import string
import time
import re
import multiprocessing
import signal
import sys
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict
from typing import Optional, Dict, List, Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from telegram import Update, ReplyKeyboardMarkup, PhotoSize
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
    Application
)
from telegram.error import NetworkError, TelegramError
import nest_asyncio

# --- Constants & Configuration ---

TELEGRAM_TOKEN = ''
ALLOWED_USERS = []
ADMINS = []
AUTH_MESSAGE = ''
SAVE_DIR = ''
NOTIFICATION_ENABLED_USERS = []

CONFIG_FILE = 'bot_config.json'
SENT_MESSAGES_FILE = 'sent_messages.json'
BOT_STATE_FILE = 'bot_state.json'
USER_CHAT_IDS_FILE = 'user_chat_ids.json'
COOKIES_FILE = 'cookies.json'
LOCALSTORAGE_FILE = 'localstorage.json'
UA_FILE = 'user_agent.txt'
DETAILS_FILE = 'deliveries.json'
NOTIFIED_FILE = 'notified.json'
ACCEPTANCE_FILE = 'acceptances.json'
ACCEPTANCE_NOTIFIED_FILE = 'acceptance_notified.json'

CHECK_URL = 'https://pvz-lk.wb.ru/upcoming-deliveries'
ACCEPTANCE_URL = 'https://pvz-lk.wb.ru/acceptance-statistics'
LOGIN_URL = 'https://pvz-lk.wb.ru/login'
ROOT_URL = 'https://pvz-lk.wb.ru/'

CHECK_INTERVAL = 180
RETRY_INTERVAL = 20

# Globals for Bot Process
USER_CHAT_IDS = {}
AUTH_STATE = 'none'  # none, waiting_phone, waiting_code, authorizing
AUTH_USER_ID = None
CODE_FUTURE = None

# Helpers for grouping incoming photo messages (Bot Process)
media_groups = defaultdict(list)
media_group_tasks = {}
media_group_base_names = {}


def load_config():
    global TELEGRAM_TOKEN, ALLOWED_USERS, ADMINS, AUTH_MESSAGE, SAVE_DIR, NOTIFICATION_ENABLED_USERS
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                TELEGRAM_TOKEN = config.get('telegram_token', '')
                ALLOWED_USERS = config.get('allowed_users', [])
                ADMINS = config.get('admins', [])
                AUTH_MESSAGE = config.get('auth_message', '')
                SAVE_DIR = Path(config.get('photo_save_path', 'photos'))
                NOTIFICATION_ENABLED_USERS = config.get('notification_enabled_users', [])
                os.makedirs(SAVE_DIR, exist_ok=True)
        except Exception as e:
            print(f"Error loading config: {e}")

load_config()

# --- Shared Helpers ---

def generate_random_groupname() -> str:
    return ''.join(random.choices(string.ascii_lowercase, k=8))

def sanitize_filename(name: str) -> str:
    return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)

def extract_first_3_words(text: str) -> str:
    words = text.strip().split()
    return sanitize_filename('_'.join(words[:3]))

def is_allowed(user) -> bool:
    return bool(user.username) and user.username in ALLOWED_USERS

def highlight_time(text: str) -> str:
    return re.sub(r"(\d{1,2}:\d{2})", r"<b>\1</b>", text)

def ensure_year(date_str: str) -> str:
    if not date_str or re.search(r"\d{4}", date_str):
        return date_str
    year = datetime.now().year
    m = re.match(r"(?P<date>\d{1,2}[\. ]\d{1,2})(?P<rest>.*)", date_str)
    if m:
        date_part = m.group('date').replace(' ', '.')
        rest = m.group('rest').strip()
        if rest:
            return f"{date_part}.{year} {rest}"
        return f"{date_part}.{year}"
    m = re.match(r"(.+?)\s+(\d{1,2}:\d{2})$", date_str)
    if m:
        return f"{m.group(1)} {year} {m.group(2)}"
    return f"{date_str} {year}"

MONTHS_RU = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
}

def _parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date_str)
    if m:
        day, month, year = map(int, m.groups())
        return date(year, month, day)
    m = re.search(r"(\d{1,2})\s+([а-яА-Я]+)\s+(\d{4})", date_str)
    if m:
        day = int(m.group(1))
        month_name = m.group(2).lower()
        year = int(m.group(3))
        month = MONTHS_RU.get(month_name)
        if month:
            return date(year, month, day)
    return None

def is_today(date_str: str) -> bool:
    d = _parse_date(ensure_year(date_str))
    return d == datetime.now().date()

# --- Data Persistence Helpers (Shared or Bot) ---

def load_deliveries():
    if Path(DETAILS_FILE).exists():
        with open(DETAILS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_deliveries(data):
    if not data:
        return
    to_save = sorted(data, key=lambda x: int(x['index']))
    with open(DETAILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(to_save, f, ensure_ascii=False)

def load_acceptances():
    if Path(ACCEPTANCE_FILE).exists():
        with open(ACCEPTANCE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_acceptances(data):
    if not data or 'date' not in data:
        return
    for item in data.get('items', []):
        item['deadline'] = ensure_year(item['deadline'])
    with open(ACCEPTANCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def load_acceptance_notified():
    if Path(ACCEPTANCE_NOTIFIED_FILE).exists():
        with open(ACCEPTANCE_NOTIFIED_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_acceptance_notified(data):
    with open(ACCEPTANCE_NOTIFIED_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(data), f, ensure_ascii=False)

def load_notified():
    if Path(NOTIFIED_FILE).exists():
        with open(NOTIFIED_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_notified(data):
    with open(NOTIFIED_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(data), f, ensure_ascii=False)

def save_sent_message(chat_id, message_id):
    messages = []
    if Path(SENT_MESSAGES_FILE).exists():
        try:
            with open(SENT_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                messages = json.load(f)
        except:
            pass
    messages.append({'chat_id': chat_id, 'message_id': message_id, 'time': time.time()})
    if len(messages) > 100:
        messages = messages[-100:]
    with open(SENT_MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f)

def save_user_chat_ids():
    with open(USER_CHAT_IDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(USER_CHAT_IDS, f, ensure_ascii=False)

def check_and_save_user_chat_id(user):
    if user.username and user.username in ALLOWED_USERS:
        if user.username not in USER_CHAT_IDS or USER_CHAT_IDS[user.username] != user.id:
            USER_CHAT_IDS[user.username] = user.id
            save_user_chat_ids()
            return True
    return False

def save_bot_state(is_authorized: bool):
    state = {'is_authorized': is_authorized, 'last_update': time.time()}
    try:
        with open(BOT_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception:
        pass

def save_config_users():
    config = {}
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            pass
    config['allowed_users'] = ALLOWED_USERS
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# --- Report Text Generators ---

def deliveries_on_the_way_text(deliveries):
    items = []
    for d in deliveries:
        if d['status'] == 'Отгружено с сортировочного центра':
            date_part, tm = d['time'].split()
            if not is_today(date_part):
                continue
            date = ensure_year(date_part)
            items.append(
                f"🚚 <b>{d['index']}-я поставка в пути</b>\n"
                f"Отгружено: <i>{highlight_time(tm)} {date}</i>\n"
                f"{d['boxes']} коробок · ~{d['shk']} ШК"
            )
    return '\n\n'.join(items) if items else 'Нет машин в пути'

def deliveries_report_text(deliveries):
    lines = ["<b>🚚 Статистика поставок за сегодня</b>"]
    if not deliveries:
        lines.append('Сегодня поставок нет')
        return '\n'.join(lines)
    total_cars = total_boxes = total_shk = 0
    for d in deliveries:
        date_part, tm = d['time'].split()
        if not is_today(date_part):
            continue
        date = ensure_year(date_part)
        lines.append(
            f"• <b>№{d['index']}</b> — {d['status']} {date} в <b>{tm}</b>\n"
            f"  {d['boxes']} коробок · ~{d['shk']} ШК"
        )
        if d['status'] == 'Прибыл':
            total_cars += 1
            total_boxes += d['boxes']
            total_shk += d['shk']
    if total_cars > 0:
        lines.append('')
        lines.append(f"<b>Итого прибыло:</b> {total_cars} машин · {total_boxes} коробок · ~{total_shk} ШК")
    return '\n'.join(lines)

def acceptance_report_text(data):
    lines = ["\n<b>📋 Статистика приемки за сегодня</b>"]
    if not data or 'items' not in data or not data['items']:
        lines.append('Нет данных о приёмке')
        return '\n'.join(lines)
    total_boxes = total_goods = total_on = total_late = 0
    for idx, item in enumerate(data['items'], 1):
        deadline = ensure_year(item['deadline'])
        if not is_today(deadline):
            continue
        lines.append(
            f"• <b>№{idx}</b> — отсчет приемки начался в {highlight_time(item['arrival'])}, принять до {highlight_time(deadline)}\n"
            f"  {item['boxes']} коробок, {item['goods']} товаров ("
            f"{item['on_time']} вовремя, {item['late']} не вовремя)"
        )
        total_boxes += item['boxes']
        total_goods += item['goods']
        total_on += item['on_time']
        total_late += item['late']
    lines.append('')
    lines.append(
        f"<b>Итого принято:</b> {total_boxes} коробок, {total_goods} товаров ("
        f"{total_on} вовремя, {total_late} не вовремя)"
    )
    return '\n'.join(lines)

def acceptance_times_text(data):
    if not data or 'items' not in data or not data['items']:
        return 'Нет данных о приёмке'
    idx = len(data['items'])
    item = data['items'][-1]
    deadline = ensure_year(item['deadline'])
    if not is_today(deadline):
        return 'Нет данных о приёмке'
    if ' ' in deadline:
        ddate, dtime = deadline.rsplit(' ', 1)
        deadline_text = f"{ddate} ⏰{highlight_time(dtime)}"
    else:
        deadline_text = highlight_time(deadline)
    arrival = highlight_time(item['arrival'])
    return (
        f"📦 <b>{idx}-й груз за сегодня</b>, отсчет приемки начался в {arrival}, "
        f"принять до {deadline_text}"
    )


# ---------------- MONITOR PROCESS ----------------

class MonitorProcess:
    def __init__(self, cmd_queue: multiprocessing.Queue, event_queue: multiprocessing.Queue):
        self.cmd_queue = cmd_queue
        self.event_queue = event_queue
        self.auth_code_future = None
        self.auth_notified = False
        self.monitor_auth_state = 'none' # none, authorizing, waiting_code
        self.last_auth_notification_time = 0

    async def run(self):
        print("Monitor: Started")
        load_config()

        # Start command listener and periodic checker
        asyncio.create_task(self.command_loop())

        # Run periodic check
        await self.check_and_notify_loop()

    async def command_loop(self):
        while True:
            try:
                # Non-blocking get from queue
                while not self.cmd_queue.empty():
                    cmd, data = self.cmd_queue.get_nowait()
                    await self.handle_command(cmd, data)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Monitor: Command loop error: {e}")
                await asyncio.sleep(1)

    async def handle_command(self, cmd, data):
        print(f"Monitor: Received command {cmd}")
        if cmd == 'auth_start':
            if self.monitor_auth_state == 'none':
                self.monitor_auth_state = 'authorizing'
                # Update Bot state
                self.event_queue.put(('auth_state', 'authorizing'))
                asyncio.create_task(self.perform_authorization(data['phone'], data['user_id']))
        elif cmd == 'auth_code':
            if self.auth_code_future and not self.auth_code_future.done():
                self.auth_code_future.set_result(data['code'])

    async def get_status_playwright(self):
        cookies = json.load(open(COOKIES_FILE, encoding='utf-8')) if Path(COOKIES_FILE).exists() else []
        localstorage = json.load(open(LOCALSTORAGE_FILE, encoding='utf-8')) if Path(LOCALSTORAGE_FILE).exists() else {}
        user_agent = open(UA_FILE, encoding='utf-8').read().strip() if Path(UA_FILE).exists() else None

        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=user_agent) if user_agent else await browser.new_context()
                if cookies:
                    await context.add_cookies(cookies)

                page = await context.new_page()
                await page.goto(CHECK_URL)
                await page.wait_for_load_state('networkidle')

                if localstorage:
                    await page.add_init_script(f"for (const [key, value] of Object.entries({json.dumps(localstorage)})) {{ localStorage.setItem(key, value); }}")
                    await page.reload()
                    await page.wait_for_load_state('networkidle')

                await asyncio.sleep(15)
                html = await page.content()

                soup = BeautifulSoup(html, 'html.parser')
                auth_header = soup.find('h2')
                current_url = page.url.split('?')[0].rstrip('/')
                if (
                    (auth_header and auth_header.find('span', string='Авторизация'))
                    or current_url in (ROOT_URL.rstrip('/'), LOGIN_URL.rstrip('/'))
                ):
                    await browser.close()
                    return None, None, True

                try:
                    header = page.locator("div.pwz-collapse-header[aria-expanded='false']")
                    if await header.count() > 0:
                        await header.first.click()
                        await page.wait_for_selector("div.pwz-collapse-content-box", timeout=7000)
                        await page.wait_for_load_state('networkidle')
                        await asyncio.sleep(1)
                except Exception:
                    pass

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                blocks = soup.find_all('div', class_='pwz-collapse-header-item upcoming-deliveries-counts pwz-collapse-header-item--separated')
                values = None
                for block in blocks:
                    label_span = block.find('span', string=lambda text: text and 'Ожидается' in text)
                    if label_span:
                        strongs = block.find_all('strong')
                        numbers = [int(s.text.strip()) for s in strongs if s.text.strip().isdigit()]
                        if len(numbers) == 3:
                            values = {'cars': numbers[0], 'boxes': numbers[1], 'shk': numbers[2]}
                        break

                deliveries = []
                today_prefix = datetime.now().strftime('%d.%m')
                content_box = soup.find('div', class_='pwz-collapse-content-box')
                if content_box:
                    for head in content_box.select('div.pwz-pwz-collapse-header'):
                        items = head.select('div.pwz-collapse-header-item')
                        if len(items) < 4: continue
                        idx = items[0].get_text(strip=True)
                        boxes = items[1].find('strong').get_text(strip=True)
                        shk = items[2].find('strong').get_text(strip=True).replace('≈', '')
                        status = items[3].select_one('span').get_text(strip=True)
                        time_str = items[3].find('strong').get_text(strip=True)
                        if today_prefix not in time_str: continue
                        try: boxes = int(boxes)
                        except ValueError: boxes = 0
                        try: shk = int(shk)
                        except ValueError: shk = 0
                        deliveries.append({'index': idx, 'boxes': boxes, 'shk': shk, 'status': status, 'time': time_str})

                await browser.close()
                return values, deliveries, False

        except Exception as e:
            print(f"Monitor: Error in get_status_playwright: {e}")
            if browser:
                try: await browser.close()
                except: pass
            return None, None, False

    async def get_acceptance_playwright(self):
        cookies = json.load(open(COOKIES_FILE, encoding='utf-8')) if Path(COOKIES_FILE).exists() else []
        localstorage = json.load(open(LOCALSTORAGE_FILE, encoding='utf-8')) if Path(LOCALSTORAGE_FILE).exists() else {}
        user_agent = open(UA_FILE, encoding='utf-8').read().strip() if Path(UA_FILE).exists() else None

        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=user_agent) if user_agent else await browser.new_context()
                if cookies: await context.add_cookies(cookies)
                page = await context.new_page()
                await page.goto(ACCEPTANCE_URL)
                await page.wait_for_load_state('networkidle')

                if localstorage:
                    await page.add_init_script(f"for (const [key, value] of Object.entries({json.dumps(localstorage)})) {{ localStorage.setItem(key, value); }}")
                    await page.reload()
                    await page.wait_for_load_state('networkidle')

                await asyncio.sleep(15)
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                auth_header = soup.find('h2')
                current_url = page.url.split('?')[0].rstrip('/')
                if (
                    (auth_header and auth_header.find('span', string='Авторизация'))
                    or current_url in (ROOT_URL.rstrip('/'), LOGIN_URL.rstrip('/'))
                ):
                    await browser.close()
                    return None, True

                try:
                    header = page.locator("div.pwz-collapse-header[aria-expanded='false']").first
                    if await header.count() > 0:
                        await header.click()
                        await page.wait_for_selector("div.pp-acceptance-list-by-day-header__header", timeout=7000)
                        await page.wait_for_load_state('networkidle')
                        await asyncio.sleep(1)
                except Exception:
                    pass

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                main = soup.select_one('div.pwz-collapse > div.pwz-collapse-item')
                if not main:
                    await browser.close()
                    return None, False

                date_span = main.select_one('div.pp-online-acceptance-list-header__date span.pwz-text--mainText')
                date_val = date_span.get_text(strip=True) if date_span else ''

                def parse_num(text):
                    m = re.search(r'\d+', text.replace('\xa0', ' '))
                    return int(m.group()) if m else 0

                items = []
                for head in main.select('div.pp-acceptance-list-by-day-header__header'):
                    cols = head.select('div.pwz-collapse-header-item')
                    if len(cols) < 5: continue
                    arrival = cols[0].find_all('span')[0].get_text(strip=True)
                    deadline = cols[0].find_all('span')[1].get_text(strip=True).replace('Принять до ', '')
                    items.append({
                        'arrival': arrival,
                        'deadline': deadline,
                        'boxes': parse_num(cols[1].get_text()),
                        'goods': parse_num(cols[2].get_text()),
                        'on_time': parse_num(cols[3].get_text()),
                        'late': parse_num(cols[4].get_text()),
                    })

                await browser.close()
                return {'date': date_val, 'items': items}, False
        except Exception as e:
            print(f"Monitor: Error in get_acceptance_playwright: {e}")
            if browser:
                try: await browser.close()
                except: pass
            return None, False

    async def check_and_notify_loop(self):
        initial_run = True
        print("Monitor: Starting check loop...")

        AUTH_NOTIFICATION_COOLDOWN = 3600

        while True:
            try:
                if self.monitor_auth_state == 'authorizing':
                    print("Monitor: Authorizing, skipping check...")
                    await asyncio.sleep(RETRY_INTERVAL)
                    continue

                print(f"Monitor: Checking... {datetime.now().strftime('%H:%M:%S')}")
                values, deliveries, need_auth = await self.get_status_playwright()
                deliveries = [d for d in (deliveries or []) if is_today(d['time'])]

                current_time = time.time()

                if need_auth:
                    print("Monitor: Auth needed")
                    if self.monitor_auth_state in ('none', 'waiting_phone'):
                         # We need user attention.
                         # We don't change state to 'waiting_phone' automatically because we need a phone number command first?
                         # Actually original code set AUTH_STATE = 'waiting_phone' and sent message.
                         # Here we notify bot to ask for auth.

                         # Grace period check
                         if current_time - self.last_auth_notification_time < 60:
                             print("Monitor: Auth needed but in grace period")
                             await asyncio.sleep(RETRY_INTERVAL)
                             continue

                         should_notify = not self.auth_notified or (current_time - self.last_auth_notification_time > AUTH_NOTIFICATION_COOLDOWN)
                         if should_notify:
                             print("Monitor: Sending auth notification")
                             self.event_queue.put(('broadcast', AUTH_MESSAGE))
                             self.auth_notified = True
                             self.last_auth_notification_time = current_time
                             save_bot_state(False)
                    await asyncio.sleep(RETRY_INTERVAL)
                    continue

                if not values:
                    print('Monitor: Failed to get data, retrying...')
                    await asyncio.sleep(RETRY_INTERVAL)
                    continue

                save_deliveries(deliveries)

                acceptance, need_auth_acc = await self.get_acceptance_playwright()
                if acceptance and not is_today(acceptance.get('date', '')):
                    acceptance = None

                if need_auth_acc:
                     print("Monitor: Auth needed (acceptance)")
                     if self.monitor_auth_state in ('none', 'waiting_phone'):
                         # Grace period check
                         if current_time - self.last_auth_notification_time < 60:
                             print("Monitor: Auth needed (acceptance) but in grace period")
                             await asyncio.sleep(RETRY_INTERVAL)
                             continue

                         should_notify = not self.auth_notified or (current_time - self.last_auth_notification_time > AUTH_NOTIFICATION_COOLDOWN)
                         if should_notify:
                             self.event_queue.put(('broadcast', AUTH_MESSAGE))
                             self.auth_notified = True
                             self.last_auth_notification_time = current_time
                             save_bot_state(False)
                     await asyncio.sleep(RETRY_INTERVAL)
                     continue

                if values and not need_auth_acc:
                    self.auth_notified = False
                    save_bot_state(True)

                if acceptance:
                    save_acceptances(acceptance)

                if initial_run:
                    text = deliveries_on_the_way_text(deliveries)
                    if text != 'Нет машин в пути':
                        self.event_queue.put(('broadcast', text))
                    initial_run = False

                notified = load_notified()
                new_deliveries_count = 0
                for d in deliveries:
                    if d['status'] == 'Отгружено с сортировочного центра' and is_today(d['time']):
                        uid = f"{d['index']}_{d['time']}"
                        if uid not in notified:
                            new_deliveries_count += 1
                            date_val, tm = d['time'].split()
                            text = (
                                f"🚚 Едет {d['index']}-я поставка за сегодня.\n"
                                f"📦 Отгружено со склада в {tm} {date_val}.\n"
                                f"{d['boxes']} коробок. ~{d['shk']} ШК."
                            )
                            self.event_queue.put(('broadcast', text))
                            notified.add(uid)
                if new_deliveries_count > 0:
                    save_notified(notified)

                if acceptance:
                    acc_notified = load_acceptance_notified()
                    new_acc = 0
                    for idx, item in enumerate(acceptance.get('items', []), start=1):
                        if not is_today(item['deadline']): continue
                        uid = f"{item['arrival']}_{item['deadline']}"
                        if uid not in acc_notified:
                            deadline = ensure_year(item['deadline'])
                            deadline_text = f"{deadline.rsplit(' ', 1)[0]} ⏰{deadline.rsplit(' ', 1)[1]}" if ' ' in deadline else deadline
                            text = (
                                f"📦 {idx}-й груз за сегодня, отсчет приемки начался в {item['arrival']}, "
                                f"принять до {deadline_text}"
                            )
                            self.event_queue.put(('broadcast', text))
                            acc_notified.add(uid)
                            new_acc += 1
                    if new_acc > 0:
                        save_acceptance_notified(acc_notified)

                print(f"Monitor: Check complete, sleeping {CHECK_INTERVAL}s")
                await asyncio.sleep(CHECK_INTERVAL)

            except Exception as e:
                print(f'Monitor: Error in check loop: {e}')
                await asyncio.sleep(RETRY_INTERVAL)

    async def perform_authorization(self, phone, user_id):
        print(f"Monitor: Starting authorization for {phone}")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(CHECK_URL)
                await asyncio.sleep(3)
                await page.wait_for_selector("input[formcontrolname='mobile']", timeout=30000)
                await page.fill("input[formcontrolname='mobile']", phone)
                await asyncio.sleep(1)
                try: await page.locator('label.opp-switcher__label').click()
                except: pass
                try:
                    btn = page.locator("button:has-text('Получить код')")
                    await btn.evaluate("e=>e.removeAttribute('disabled')")
                    await btn.click()
                except: pass
                
                print("Monitor: Waiting for code input...")
                await page.wait_for_selector("input[formcontrolname='code']", timeout=120000)
                
                # Request code from bot
                self.monitor_auth_state = 'waiting_code'
                self.event_queue.put(('auth_state', 'waiting_code'))
                self.event_queue.put(('request_code', {'user_id': user_id}))
                
                self.auth_code_future = asyncio.get_running_loop().create_future()
                code = await self.auth_code_future
                
                await page.fill("input[formcontrolname='code']", code)
                await asyncio.sleep(1)
                try:
                    login_btn = page.locator("button:has-text('Войти')")
                    await login_btn.evaluate("e=>e.removeAttribute('disabled')")
                    await login_btn.click()
                except: pass

                await asyncio.sleep(15)
                cookies = await context.cookies()
                with open(COOKIES_FILE, 'w', encoding='utf-8') as f: json.dump(cookies, f)
                localstorage = await page.evaluate('''() => {let o={};for(let i=0;i<localStorage.length;i++){let k=localStorage.key(i);o[k]=localStorage.getItem(k);}return o;}''')
                with open(LOCALSTORAGE_FILE, 'w', encoding='utf-8') as f: json.dump(localstorage, f)
                ua = await page.evaluate("navigator.userAgent")
                with open(UA_FILE, 'w', encoding='utf-8') as f: f.write(ua)

                self.event_queue.put(('auth_success', {'user_id': user_id}))
                self.monitor_auth_state = 'none'
                self.auth_code_future = None
                self.auth_notified = False
                self.last_auth_notification_time = time.time()
                self.event_queue.put(('auth_state', 'none'))
                save_bot_state(True)
                await browser.close()

        except Exception as e:
            print(f"Monitor: Auth error: {e}")
            self.event_queue.put(('auth_failed', {'user_id': user_id, 'error': str(e)}))
            self.monitor_auth_state = 'none'
            self.auth_code_future = None
            self.event_queue.put(('auth_state', 'none'))
            save_bot_state(False)


def run_monitor_process(cmd_queue, event_queue):
    monitor = MonitorProcess(cmd_queue, event_queue)
    asyncio.run(monitor.run())

# ---------------- BOT PROCESS ----------------

async def send_notification_to_users(app: Application, message: str, exclude_user_id=None):
    load_config() # Reload config to check enabled users
    sent_count = 0
    failed_count = 0
    for username in ALLOWED_USERS:
        if username not in NOTIFICATION_ENABLED_USERS:
            continue
        if username in USER_CHAT_IDS:
            chat_id = USER_CHAT_IDS[username]
            if exclude_user_id and chat_id == exclude_user_id:
                continue
            try:
                msg = await app.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
                save_sent_message(chat_id, msg.message_id)
                sent_count += 1
            except Exception as e:
                print(f"Failed to send to @{username}: {e}")
                failed_count += 1
        else:
            failed_count += 1
    return sent_count, failed_count

async def bot_event_listener(app: Application, event_queue: multiprocessing.Queue):
    global AUTH_STATE
    while True:
        try:
            while not event_queue.empty():
                event, data = event_queue.get_nowait()
                print(f"Bot: Received event {event}")

                if event == 'broadcast':
                    await send_notification_to_users(app, data)

                elif event == 'auth_state':
                    AUTH_STATE = data

                elif event == 'request_code':
                    user_id = data['user_id']
                    await app.bot.send_message(chat_id=user_id, text='Введите код подтверждения из приложения')

                elif event == 'auth_success':
                    user_id = data['user_id']
                    await app.bot.send_message(chat_id=user_id, text='Авторизация завершена')

                elif event == 'auth_failed':
                    user_id = data['user_id']
                    error = data['error']
                    msg = 'Ошибка авторизации: Время ожидания истекло.' if "Timeout" in error else f'Ошибка авторизации: {error}'
                    await app.bot.send_message(chat_id=user_id, text=msg)
            
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Bot: Event listener error: {e}")
            await asyncio.sleep(1)

async def wait_and_process_group(media_group_id, context):
    await asyncio.sleep(2.0)
    messages = media_groups.pop(media_group_id, [])
    base_name = media_group_base_names.pop(media_group_id, generate_random_groupname())
    media_group_tasks.pop(media_group_id, None)
    if messages:
        await save_photos(messages, context, base_name)

async def save_photos(messages, context, base_name):
    load_config()
    for idx, msg in enumerate(messages, start=1):
        if not msg.photo: continue
        file: PhotoSize = await msg.photo[-1].get_file()
        filename = f"{base_name}_{idx}.jpg"
        path = os.path.join(SAVE_DIR, filename)
        await file.download_to_drive(path)
    await context.bot.set_message_reaction(
        chat_id=messages[0].chat_id,
        message_id=messages[0].message_id,
        reaction=['👍'],
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_IDS
    user = update.effective_user
    if not is_allowed(user):
        return
    check_and_save_user_chat_id(user)

    message = update.message
    media_group_id = message.media_group_id

    if media_group_id:
        media_groups[media_group_id].append(message)
        if media_group_id not in media_group_base_names:
            caption = message.caption.strip() if message.caption else None
            base_name = extract_first_3_words(caption) if caption else generate_random_groupname()
            media_group_base_names[media_group_id] = base_name

        if media_group_id not in media_group_tasks:
            media_group_tasks[media_group_id] = asyncio.create_task(
                wait_and_process_group(media_group_id, context)
            )
    else:
        caption = message.caption.strip() if message.caption else None
        base_name = extract_first_3_words(caption) if caption else generate_random_groupname()
        await save_photos([message], context, base_name)

async def delete_previous_messages(app):
    if not Path(SENT_MESSAGES_FILE).exists(): return
    try:
        with open(SENT_MESSAGES_FILE, 'r', encoding='utf-8') as f: messages = json.load(f)
        for msg in messages:
            try:
                await app.bot.delete_message(chat_id=msg['chat_id'], message_id=msg['message_id'])
                await asyncio.sleep(0.1)
            except: pass
        with open(SENT_MESSAGES_FILE, 'w', encoding='utf-8') as f: json.dump([], f)
    except Exception as e: print(f"Error deleting messages: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTH_STATE, AUTH_USER_ID, USER_CHAT_IDS
    user = update.effective_user
    text = update.message.text.strip()
    lower = text.lower()
    
    check_and_save_user_chat_id(user)

    # Admin commands
    if user.username in ADMINS:
        if lower.startswith('добавить '):
            username = text.split(maxsplit=1)[1].lstrip('@')
            if username not in ALLOWED_USERS:
                ALLOWED_USERS.append(username)
                save_config_users()
                msg = f'✅ @{username} добавлен'
                if username not in USER_CHAT_IDS: msg += '\n⚠️ Пользователь должен написать боту'
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text(f'@{username} уже есть в списке')
            return
        if lower.startswith('удалить '):
            username = text.split(maxsplit=1)[1].lstrip('@')
            if username in ALLOWED_USERS:
                ALLOWED_USERS.remove(username)
                save_config_users()
                await update.message.reply_text(f'@{username} удалён')
            else:
                await update.message.reply_text(f'@{username} не найден')
            return
        if lower == 'статус':
            status_text = "📊 Статус пользователей:\n\n"
            for username in ALLOWED_USERS:
                status = "активен" if username in USER_CHAT_IDS else "не писал боту"
                status_text += f"✅ @{username} - {status}\n"
            await update.message.reply_text(status_text)
            return
        if lower.startswith('написать всем'):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                await update.message.reply_text('Не указан текст')
                return
            message = parts[2]
            sent_count, failed_count = await send_notification_to_users(context.application, message, exclude_user_id=user.id)
            await update.message.reply_text(f'Отправлено: {sent_count}, Ошибок: {failed_count}')
            return

    # Auth logic
    # Check if we are waiting for code (Global state synced from Monitor)
    if AUTH_STATE == 'waiting_code' and re.fullmatch(r'\d{6}', text) and user.id == AUTH_USER_ID:
        # Send code to monitor
        context.bot_data['cmd_queue'].put(('auth_code', {'code': text}))
        await update.message.reply_text('Код получен, отправляю...')
        return

    if is_allowed(user) and re.fullmatch(r'[+]?[-()\s\d]{10,}', text) and AUTH_STATE != 'waiting_code':
        phone_digits = ''.join(filter(str.isdigit, text))
        phone = phone_digits[-10:]
        AUTH_USER_ID = user.id
        await update.message.reply_text('Ввожу номер...')
        # Send auth start to monitor
        context.bot_data['cmd_queue'].put(('auth_start', {'phone': phone, 'user_id': user.id}))
        return

    if user.username not in ALLOWED_USERS:
         admins_list = ", ".join([f"@{a}" for a in ADMINS])
         await update.message.reply_text(f'⛔️ Нет доступа. Обратитесь к {admins_list}')
         return

    # Standard commands
    deliveries = load_deliveries()
    acceptance = load_acceptances()
    keyboard = ReplyKeyboardMarkup([['В пути', 'Отчёт', 'Время на приемку']], resize_keyboard=True)

    if lower == 'в пути':
        await update.message.reply_text(deliveries_on_the_way_text(deliveries), reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif lower in ('отчёт', 'отчет'):
        text = deliveries_report_text(deliveries) + '\n' + acceptance_report_text(acceptance)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif lower.startswith('время на приемк'):
        await update.message.reply_text(acceptance_times_text(acceptance), reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text('Выберите команду:', reply_markup=keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    check_and_save_user_chat_id(user)
    if user.username in ALLOWED_USERS:
        await update.message.reply_text(
            'Привет! Бот уведомляет о поставках и времени приёмки.',
            reply_markup=ReplyKeyboardMarkup([['В пути', 'Отчёт', 'Время на приемку']], resize_keyboard=True),
            parse_mode=ParseMode.HTML,
        )
    else:
        admins_list = ", ".join([f"@{a}" for a in ADMINS])
        await update.message.reply_text(f'⛔️ Нет доступа. Обратитесь к {admins_list}')

async def main():
    print("Bot Process: Starting...")
    load_config()
    
    # Load chat IDs
    global USER_CHAT_IDS
    if Path(USER_CHAT_IDS_FILE).exists():
        with open(USER_CHAT_IDS_FILE, 'r', encoding='utf-8') as f:
            USER_CHAT_IDS = json.load(f)

    # Initialize Queues
    cmd_queue = multiprocessing.Queue()
    event_queue = multiprocessing.Queue()

    # Start Monitor Process
    monitor = multiprocessing.Process(target=run_monitor_process, args=(cmd_queue, event_queue))
    monitor.daemon = True
    monitor.start()
    print(f"Bot Process: Monitor process started with PID {monitor.pid}")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Store queues in bot_data to access in handlers
    app.bot_data['cmd_queue'] = cmd_queue
    app.bot_data['event_queue'] = event_queue

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    
    await delete_previous_messages(app)
    
    # Start event listener
    asyncio.create_task(bot_event_listener(app, event_queue))
    
    print("Bot Process: Running polling...")

    # Run polling (blocking)
    try:
        await app.run_polling()
    except Exception as e:
        print(f"Bot Process: Polling error: {e}")
    finally:
        print("Bot Process: Stopping monitor...")
        monitor.terminate()
        monitor.join()

if __name__ == '__main__':
    nest_asyncio.apply()
    # On Windows, we need to call freeze_support()
    multiprocessing.freeze_support()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
