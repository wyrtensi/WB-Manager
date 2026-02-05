/**
 * WB Manager - Основной JavaScript v2.0
 * Улучшенный функционал с QR-модалками и clipboard
 */

// ========== API HELPERS ==========

const API = {
    async get(endpoint) {
        const response = await fetch(`/api${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    },
    
    async post(endpoint, data) {
        const response = await fetch(`/api${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    },
    
    async delete(endpoint) {
        const response = await fetch(`/api${endpoint}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }
};

// ========== TOAST NOTIFICATIONS ==========

const Toast = {
    container: null,
    
    init() {
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
    },
    
    show(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`,
            error: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
            info: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`
        };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
        `;
        
        this.container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'toastIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    persistent(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icons = {
            success: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`,
            error: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
            info: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
        `;

        this.container.appendChild(toast);
        // Не убираем автоматически, но добавляем анимацию появления
        toast.style.animation = 'none'; // Сброс
        setTimeout(() => toast.style.animation = 'toastIn 0.3s ease forwards', 10);

        return {
            update(newMessage) {
                const msgEl = toast.querySelector('.toast-message');
                if (msgEl) msgEl.textContent = newMessage;
            },
            remove() {
                toast.style.animation = 'toastIn 0.3s ease reverse';
                setTimeout(() => toast.remove(), 300);
            }
        };
    },
    
    success(message) { this.show(message, 'success'); },
    error(message) { this.show(message, 'error'); },
    info(message) { this.show(message, 'info'); }
};

// ========== CLIPBOARD ==========

async function copyToClipboard(text, element = null) {
    try {
        await navigator.clipboard.writeText(text);
        
        // Визуальный фидбек на элементе
        if (element) {
            const originalText = element.innerHTML;
            element.innerHTML = '✓ Скопировано!';
            element.classList.add('copied');
            setTimeout(() => {
                element.innerHTML = originalText;
                element.classList.remove('copied');
            }, 1500);
        }
        
        Toast.success(`Скопировано: ${text}`);
    } catch (err) {
        Toast.error('Не удалось скопировать');
    }
}

// ========== FORMATTING HELPERS ==========

const DEFAULT_SERVER_TZ_OFFSET_MS = 3 * 60 * 60 * 1000; // Москва (UTC+3)
const MONTHS_LONG_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

function maskPhoneParts(phone) {
    const digits = String(phone || '').replace(/\D/g, '');
    if (!digits) return null;
    let normalized = digits;
    if (normalized.length === 10 && normalized.startsWith('9')) {
        normalized = `7${normalized}`;
    } else if (normalized.length === 11 && normalized.startsWith('8')) {
        normalized = `7${normalized.slice(1)}`;
    }
    const suffixLength = Math.min(4, normalized.length);
    const prefixLength = normalized.length > 7
        ? 3
        : Math.max(0, normalized.length - suffixLength);
    const first = prefixLength ? normalized.slice(0, prefixLength) : '';
    const last = suffixLength ? normalized.slice(-suffixLength) : '';
    const hasHidden = normalized.length > (prefixLength + suffixLength);
    const base = `+${first}${hasHidden ? 'xxxx' : ''}`;
    return {
        text: `${base}${last}`,
        base,
        highlight: last
    };
}

function formatPhone(phone) {
    const parts = maskPhoneParts(phone);
    if (!parts) return '';
    if (!parts.highlight) return parts.text;
    return `${parts.base}<span class="highlight">${parts.highlight}</span>`;
}

function formatPhonePlain(phone) {
    const parts = maskPhoneParts(phone);
    return parts ? parts.text : '';
}

function parseTimestamp(value) {
    if (value === null || value === undefined) {
        return null;
    }
    if (value instanceof Date) {
        return value;
    }
    if (typeof value === 'number') {
        const ms = value >= 1e12 ? value : value * 1000; // seconds -> ms
        return new Date(ms);
    }
    if (typeof value === 'string') {
        const trimmed = value.trim();
        if (!trimmed) return null;
        if (/^\d+$/.test(trimmed)) {
            const num = parseInt(trimmed, 10);
            const ms = trimmed.length >= 13 ? num : num * 1000;
            return new Date(ms);
        }
        const normalized = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T');
        if (/[+-]\d{2}:?\d{2}$/.test(normalized) || normalized.endsWith('Z')) {
            return new Date(normalized);
        }
        const simpleMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);
        if (simpleMatch) {
            const [, y, m, d, hh, mm, ss = '0'] = simpleMatch;
            const utcMs = Date.UTC(
                parseInt(y, 10),
                parseInt(m, 10) - 1,
                parseInt(d, 10),
                parseInt(hh, 10),
                parseInt(mm, 10),
                parseInt(ss, 10)
            );
            return new Date(utcMs - DEFAULT_SERVER_TZ_OFFSET_MS);
        }
        return new Date(normalized);
    }
    return null;
}

function formatDate(timestamp, options = {}) {
    const date = parseTimestamp(timestamp);
    if (!date || Number.isNaN(date.getTime())) {
        return '';
    }
    const { withSeconds = false, verbose = false } = options;
    const day = String(date.getDate()).padStart(2, '0');
    const monthNumeric = String(date.getMonth() + 1).padStart(2, '0');
    const monthLong = MONTHS_LONG_RU[date.getMonth()];
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    const timePart = withSeconds ? `${hours}:${minutes}:${seconds}` : `${hours}:${minutes}`;
    if (verbose) {
        return `${day} ${monthLong} ${year} в ${timePart}`;
    }
    return `${day}.${monthNumeric}.${year} ${timePart}`;
}

function formatPrice(price) {
    if (!price) return '0 ₽';
    const num = typeof price === 'number' ? price : parseInt(price);
    return num + ' ₽';
}

// ========== IMAGE RETRY ==========

// Кэш найденных рабочих URL (с сохранением в localStorage)
const workingImageUrls = (() => {
    try {
        const cached = JSON.parse(localStorage.getItem('workingImageUrls') || '{}');
        console.log(`[ImageCache] Загружено ${Object.keys(cached).length} URL из кэша`);
        return cached;
    } catch {
        return {};
    }
})();

// Кэш неудачных попыток (чтобы не повторять в этой сессии)
const failedImageUrls = new Set();

// Очереди для загрузки картинок: приоритетная (видимые) и фоновая
const priorityImageQueue = []; // Картинки на экране - высокий приоритет
const backgroundImageQueue = []; // Фоновая предзагрузка - низкий приоритет
let activeRequests = 0;
const MAX_CONCURRENT_REQUESTS = 2; // Минимум для избежания перегрузки соединений
let pendingCacheSave = false;

// Настройки фоновой загрузки изображений
const AUTO_IMAGE_LOADING_STORAGE_KEY = 'autoImageLoadingEnabled';
let autoImageLoadingEnabled = false;
const backgroundVendorPool = new Set();
let idlePreloadHandle = null;
let vendorRefreshTimer = null;
let vendorCodesFetchPromise = null;
const BACKGROUND_BATCH_SIZE = 40;
const BACKGROUND_IDLE_TIMEOUT = 1500;

const requestIdle = typeof window !== 'undefined' && window.requestIdleCallback
    ? window.requestIdleCallback.bind(window)
    : (cb) => setTimeout(() => cb({ timeRemaining: () => 0 }), 200);
const cancelIdle = typeof window !== 'undefined' && window.cancelIdleCallback
    ? window.cancelIdleCallback.bind(window)
    : (handle) => clearTimeout(handle);
const IMAGE_BATCH_CHUNK = 40;

function processNodesIdle(nodes, handler, options = {}) {
    const list = Array.isArray(nodes) ? nodes : Array.from(nodes || []);
    if (!list.length) {
        if (typeof options.onDone === 'function') {
            options.onDone();
        }
        return;
    }
    const chunkSize = options.chunkSize || IMAGE_BATCH_CHUNK;
    let index = 0;
    const runner = (deadline) => {
        let processed = 0;
        while (index < list.length) {
            handler(list[index], index);
            index += 1;
            processed += 1;
            const timeLeft = deadline && typeof deadline.timeRemaining === 'function'
                ? deadline.timeRemaining()
                : Infinity;
            if (processed >= chunkSize && timeLeft < 5) {
                break;
            }
        }
        if (index < list.length) {
            requestIdle(runner, { timeout: options.timeout || 200 });
        } else if (typeof options.onDone === 'function') {
            options.onDone();
        }
    };
    requestIdle(runner, { timeout: options.timeout || 50 });
}

function scheduleHydrationTask(fn, options = {}) {
    if (typeof fn !== 'function') return;
    const { timeout = 600, raf = true } = options;
    const runner = () => requestIdle(() => fn(), { timeout });
    if (raf && typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(runner);
    } else {
        runner();
    }
}
const vendorImageRegistry = new Map();
const imageVendorMap = new WeakMap();
let imageLoadingDisabledToastTs = 0;

function saveImageCache() {
    // Debounce - сохраняем не чаще раза в секунду
    if (pendingCacheSave) return;
    pendingCacheSave = true;
    
    setTimeout(() => {
        pendingCacheSave = false;
        try {
            // Сохраняем все записи без ограничений
            localStorage.setItem('workingImageUrls', JSON.stringify(workingImageUrls));
            console.log(`[ImageCache] Сохранено ${Object.keys(workingImageUrls).length} URL`);
        } catch (e) {
            // Если localStorage переполнен - очищаем старые записи
            if (e.name === 'QuotaExceededError') {
                console.warn('[ImageCache] localStorage переполнен, очищаем старые записи');
                const entries = Object.entries(workingImageUrls);
                const toKeep = entries.slice(-Math.floor(entries.length / 2));
                const newCache = Object.fromEntries(toKeep);
                Object.keys(workingImageUrls).forEach(k => delete workingImageUrls[k]);
                Object.assign(workingImageUrls, newCache);
                localStorage.setItem('workingImageUrls', JSON.stringify(newCache));
            } else {
                console.warn('[ImageCache] Ошибка сохранения:', e);
            }
        }
    }, 1000);
}

// ========== IMAGE LOADING SETTINGS ==========

function isAutoImageLoadingEnabled() {
    return autoImageLoadingEnabled;
}

function persistAutoImageLoadingSetting(enabled) {
    try {
        localStorage.setItem(AUTO_IMAGE_LOADING_STORAGE_KEY, enabled ? 'true' : 'false');
    } catch {
        /* ignore quota issues */
    }
}

function notifyAutoImageToggle(enabled) {
    const message = enabled
        ? 'Фоновая загрузка картинок включена'
        : 'Фоновая загрузка картинок отключена';
    if (typeof Toast !== 'undefined' && Toast.container) {
        Toast.info(message);
    } else {
        console.log(`[ImageLoader] ${message}`);
    }
}

function updateAutoImageLoadingState(enabled, options = {}) {
    const { persist = true, silent = false } = options;
    const normalized = Boolean(enabled);
    if (normalized === autoImageLoadingEnabled && !options.force) {
        return;
    }
    autoImageLoadingEnabled = normalized;
    if (persist) {
        persistAutoImageLoadingSetting(autoImageLoadingEnabled);
    }
    syncAutoImageToggleUI();
    if (autoImageLoadingEnabled) {
        startGlobalImagePreload(true);
        processImageQueue();
    } else {
        stopGlobalImagePreload();
    }
    if (!silent) {
        notifyAutoImageToggle(autoImageLoadingEnabled);
    }
}

function enqueueBackgroundVendors(codes = []) {
    if (!isAutoImageLoadingEnabled()) return;
    if (!codes || !codes.length) return;
    let added = 0;
    codes.forEach(rawCode => {
        const code = rawCode ? String(rawCode) : '';
        if (!code) return;
        if (workingImageUrls[code] || failedImageUrls.has(code)) return;
        if (backgroundVendorPool.has(code)) return;
        backgroundVendorPool.add(code);
        added++;
    });
    if (added > 0) {
        scheduleBackgroundBatch();
    }
}

function scheduleBackgroundBatch() {
    if (!isAutoImageLoadingEnabled()) return;
    if (idlePreloadHandle !== null) return;
    const runner = (deadline) => {
        idlePreloadHandle = null;
        if (!isAutoImageLoadingEnabled()) return;
        const batch = [];
        let capacity = BACKGROUND_BATCH_SIZE;
        if (deadline && typeof deadline.timeRemaining === 'function') {
            const remaining = Math.max(deadline.timeRemaining(), 0);
            if (remaining < 10) {
                capacity = Math.max(10, Math.floor(remaining));
            } else {
                capacity = Math.min(80, Math.floor(remaining * 2));
            }
        }
        while (capacity > 0 && backgroundVendorPool.size > 0) {
            const iterator = backgroundVendorPool.values().next();
            if (iterator.done) break;
            const code = iterator.value;
            backgroundVendorPool.delete(code);
            if (!workingImageUrls[code] && !failedImageUrls.has(code)) {
                batch.push(code);
                capacity--;
            }
        }
        batch.forEach(code => queueImage(null, code, false));
        if (batch.length) {
            processImageQueue();
        }
        if (backgroundVendorPool.size > 0 && isAutoImageLoadingEnabled()) {
            scheduleBackgroundBatch();
        }
    };
    idlePreloadHandle = requestIdle(runner, { timeout: BACKGROUND_IDLE_TIMEOUT });
}

async function fetchAndQueueVendorCodes(force = false) {
    if (!isAutoImageLoadingEnabled()) return;
    if (vendorCodesFetchPromise && !force) return vendorCodesFetchPromise;
    vendorCodesFetchPromise = (async () => {
        try {
            const response = await fetch('/api/vendor-codes');
            const data = await response.json();
            if (Array.isArray(data.codes)) {
                enqueueBackgroundVendors(data.codes);
            }
            lastVendorCodesCheck = Date.now();
        } catch (err) {
            console.error('[ImagePreload] Ошибка загрузки vendor_code:', err);
        } finally {
            vendorCodesFetchPromise = null;
        }
    })();
    return vendorCodesFetchPromise;
}

function startGlobalImagePreload(forceFetch = false) {
    if (!isAutoImageLoadingEnabled()) return;
    checkForNewProducts(forceFetch);
    if (!vendorRefreshTimer) {
        vendorRefreshTimer = setInterval(() => checkForNewProducts(), VENDOR_CODES_CHECK_INTERVAL);
    }
    scheduleBackgroundBatch();
}

function stopGlobalImagePreload() {
    if (vendorRefreshTimer) {
        clearInterval(vendorRefreshTimer);
        vendorRefreshTimer = null;
    }
    if (idlePreloadHandle !== null) {
        cancelIdle(idlePreloadHandle);
        idlePreloadHandle = null;
    }
    backgroundVendorPool.clear();
    priorityImageQueue.length = 0;
    backgroundImageQueue.length = 0;
    activeRequests = 0;
}

function initAutoImageLoadingControls() {
    // Автозагрузка отключена
}

function syncAutoImageToggleUI() {
    // Автозагрузка отключена
}


function escapeVendorSelector(code) {
    if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
        return CSS.escape(code);
    }
    return String(code).replace(/([\.\[\]\(\)\{\}\*\+\?\^\$\|])/g, '\\$1');
}

function registerVendorImage(img, vendorCode) {
    if (!img || !vendorCode) return;
    const code = String(vendorCode);
    const existing = imageVendorMap.get(img);
    if (existing && existing !== code) {
        const prevSet = vendorImageRegistry.get(existing);
        if (prevSet) {
            prevSet.delete(img);
            if (!prevSet.size) vendorImageRegistry.delete(existing);
        }
    }
    imageVendorMap.set(img, code);
    let bucket = vendorImageRegistry.get(code);
    if (!bucket) {
        bucket = new Set();
        vendorImageRegistry.set(code, bucket);
    }
    bucket.add(img);
}

function unregisterVendorImage(img) {
    if (!img) return;
    const code = imageVendorMap.get(img);
    if (!code) return;
    const bucket = vendorImageRegistry.get(code);
    if (bucket) {
        bucket.delete(img);
        if (!bucket.size) vendorImageRegistry.delete(code);
    }
    imageVendorMap.delete(img);
}

function collectVendorImages(vendorCode) {
    const code = vendorCode ? String(vendorCode) : '';
    if (!code) return [];
    let bucket = vendorImageRegistry.get(code);
    if (!bucket || !bucket.size) {
        const selector = `img[data-vendor="${escapeVendorSelector(code)}"]`;
        document.querySelectorAll(selector).forEach(img => registerVendorImage(img, code));
        bucket = vendorImageRegistry.get(code);
    }
    return bucket ? Array.from(bucket) : [];
}

function setVendorImagesSource(vendorCode, url) {
    const targets = collectVendorImages(vendorCode);
    let updated = 0;
    targets.forEach(img => {
        if (!img.isConnected) {
            unregisterVendorImage(img);
            return;
        }
        if (url && img.src !== url) {
            img.src = url;
        }
        img.classList.remove('pending-image');
        updated++;
    });
    return updated;
}

function markVendorImagesPending(vendorCode) {
    collectVendorImages(vendorCode).forEach(img => {
        if (!img.isConnected) {
            unregisterVendorImage(img);
            return;
        }
        img.src = '/static/img/no-image.svg';
        img.classList.add('pending-image');
    });
}

// Проверка видимости элемента на экране
function isElementVisible(el) {
    if (!el || !el.isConnected) return false;
    const rect = el.getBoundingClientRect();
    return rect.top < window.innerHeight && rect.bottom > 0;
}

// Добавить в очередь с приоритетом
function queueImage(img, vendorCode, priority = false, force = false) {
    const code = vendorCode ? String(vendorCode) : '';
    if (!code) return;
    if (img) registerVendorImage(img, code);
    if (!force && !isAutoImageLoadingEnabled()) {
        return;
    }
    if (failedImageUrls.has(code) || workingImageUrls[code]) {
        if (workingImageUrls[code]) {
            setVendorImagesSource(code, workingImageUrls[code]);
        }
        return;
    }
    
    const item = { img, vendorCode: code };
    if (priority) {
        if (!priorityImageQueue.some(i => i.vendorCode === code)) {
            priorityImageQueue.push(item);
        }
    } else if (!priorityImageQueue.some(i => i.vendorCode === code) &&
               !backgroundImageQueue.some(i => i.vendorCode === code)) {
        backgroundImageQueue.push(item);
    }
}

let isProcessingQueue = false;

function processImageQueue() {
    if (!isAutoImageLoadingEnabled()) {
        isProcessingQueue = false;
        return;
    }
    if (isProcessingQueue) return;
    isProcessingQueue = true;
    
    processNextBatch();
}

function processNextBatch() {
    if (!isAutoImageLoadingEnabled()) {
        isProcessingQueue = false;
        return;
    }
    // Обрабатываем по одному за раз с небольшой задержкой
    if (activeRequests >= MAX_CONCURRENT_REQUESTS) {
        isProcessingQueue = false;
        return;
    }
    
    let item = priorityImageQueue.shift() || backgroundImageQueue.shift();
    if (!item) {
        isProcessingQueue = false;
        return;
    }
    
    const { img, vendorCode } = item;
    
    // Пропускаем если уже знаем что картинки нет или уже в кэше
    if (failedImageUrls.has(vendorCode)) {
        processNextBatch(); // Без задержки
        return;
    }
    if (workingImageUrls[vendorCode]) {
        setVendorImagesSource(vendorCode, workingImageUrls[vendorCode]);
        processNextBatch(); // Без задержки
        return;
    }
    
    activeRequests++;
    
    // Быстрый запрос - получаем URL по алгоритму (без проверки)
    fetch(`/api/image/${vendorCode}?size=small`)
        .then(res => res.json())
        .then(data => {
            if (data.url) {
                // Проверяем что картинка реально загружается
                const testImg = new Image();
                testImg.onload = function() {
                    if (this.naturalWidth > 0 && this.naturalHeight > 0) {
                        // Картинка загрузилась успешно
                        workingImageUrls[vendorCode] = data.url;
                        saveImageCache();
                        setVendorImagesSource(vendorCode, data.url);
                    } else {
                        // Пустая картинка - ищем рабочий URL
                        findWorkingUrl(vendorCode);
                    }
                };
                testImg.onerror = function() {
                    // Ошибка загрузки - ищем рабочий URL
                    findWorkingUrl(vendorCode);
                };
                testImg.src = data.url;
            } else {
                failedImageUrls.add(vendorCode);
            }
        })
        .catch(() => {
            // При ошибке сети - не помечаем как failed, может попробуем позже
        })
        .finally(() => {
            activeRequests--;
            // Задержка между запросами для избежания перегрузки TCP
            setTimeout(processNextBatch, 100);
        });
}

// Поиск рабочего URL через сервер (проверяет разные basket серверы)
function findWorkingUrl(vendorCode) {
    fetch(`/api/image/find/${vendorCode}?size=small`)
        .then(res => res.json())
        .then(data => {
            if (data.found && data.url) {
                workingImageUrls[vendorCode] = data.url;
                saveImageCache();
                setVendorImagesSource(vendorCode, data.url);
            } else {
                failedImageUrls.add(vendorCode);
            }
        })
        .catch(() => {
            failedImageUrls.add(vendorCode);
        });
}

function retryImage(img) {
    // Не обрабатываем заглушку
    if (img.src.includes('no-image.svg')) {
        return;
    }
    
    // Извлекаем vendor_code из атрибута data-vendor или из URL
    let vendorCode = img.dataset.vendor;
    if (!vendorCode) {
        const match = img.src.match(/\/(\d+)\/images\//);
        if (!match) {
            img.src = '/static/img/no-image.svg';
            return;
        }
        vendorCode = match[1];
    }

    // BREAK THE LOOP: Если текущий (сбойный) src совпадает с тем что в кэше - удаляем из кэша
    if (workingImageUrls[vendorCode]) {
        // img.src - полный URL, workingImageUrls - часто относительный
        if (img.src.endsWith(workingImageUrls[vendorCode]) || img.src === workingImageUrls[vendorCode]) {
            console.warn(`[ImageLoader] Cached URL failed for ${vendorCode}, removing from cache`);
            delete workingImageUrls[vendorCode];
            saveImageCache();
        }
    }
    
    // Регистрируем, чтобы дальнейшие обновления сработали мгновенно
    registerVendorImage(img, vendorCode);
    // Проверяем кэш - мгновенно (только если там что-то осталось после проверки выше)
    if (workingImageUrls[vendorCode]) {
        setVendorImagesSource(vendorCode, workingImageUrls[vendorCode]);
        return;
    }
    
    // Если уже пробовали и не нашли - показываем заглушку
    if (failedImageUrls.has(vendorCode)) {
        markVendorImagesPending(vendorCode);
        return;
    }
    
    // Для автоматических попыток (через onerror) - не делаем ничего если автозагрузка выключена
    if (!isAutoImageLoadingEnabled()) {
        markVendorImagesPending(vendorCode);
        return;
    }
    
    // Показываем заглушку пока ищем
    markVendorImagesPending(vendorCode);
    
    // Делаем поиск рабочего URL (с проверкой разных серверов)
    fetch(`/api/image/find/${vendorCode}?size=small`)
        .then(res => res.json())
        .then(data => {
            if (data.found && data.url) {
                workingImageUrls[vendorCode] = data.url;
                saveImageCache();
                setVendorImagesSource(vendorCode, data.url);
            } else {
                failedImageUrls.add(vendorCode);
            }
        })
        .catch(() => {
            failedImageUrls.add(vendorCode);
        });
}

// Делаем функции глобальными для inline onerror
window.retryImage = retryImage;

function resolveImageUrl(vendorCode, fallbackUrl) {
    const code = vendorCode ? String(vendorCode) : '';
    if (code && workingImageUrls[code]) {
        return workingImageUrls[code];
    }
    if (fallbackUrl && !fallbackUrl.includes('no-image')) {
        return fallbackUrl;
    }
    if (!isAutoImageLoadingEnabled()) {
        return '/static/img/no-image.svg';
    }
    return '/static/img/no-image.svg';
}

function getInitialImageSrc(vendorCode, fallbackUrl) {
    const code = vendorCode ? String(vendorCode) : '';
    if (code && workingImageUrls[code]) {
        return workingImageUrls[code];
    }
    if (fallbackUrl && !fallbackUrl.includes('no-image')) {
        return fallbackUrl;
    }
    return '/static/img/no-image.svg';
}

function hydrateVendorImages(scope, selector, priority = false, options = {}) {
    if (!scope) return;
    const images = scope.querySelectorAll(selector);
    if (!images.length) return;
    const run = () => {
        const loadingAllowed = isAutoImageLoadingEnabled();
        let queued = 0;
        processNodesIdle(images, (img) => {
            const vendorCode = img.dataset.vendor;
            const fallbackUrl = img.dataset.fallback;
            if (!vendorCode) {
                if (loadingAllowed && fallbackUrl && !fallbackUrl.includes('no-image')) {
                    img.src = fallbackUrl;
                    img.classList.remove('pending-image');
                }
                return;
            }
            registerVendorImage(img, vendorCode);
            const cachedUrl = workingImageUrls[vendorCode];
            if (cachedUrl) {
                img.src = cachedUrl;
                img.classList.remove('pending-image');
                return;
            }

            if (fallbackUrl && !fallbackUrl.includes('no-image')) {
                img.src = fallbackUrl;
                img.classList.remove('pending-image');
                return;
            }

            if (failedImageUrls.has(vendorCode) || !loadingAllowed) {
                return;
            }
            const isPriority = priority || isElementVisible(img);
            queueImage(img, vendorCode, isPriority);
            queued += 1;
        }, {
            chunkSize: options.chunkSize,
            onDone: () => {
                if (queued > 0 && isAutoImageLoadingEnabled()) {
                    processImageQueue();
                }
                if (typeof options.onDone === 'function') {
                    options.onDone();
                }
            }
        });
    };
    if (options.defer) {
        requestAnimationFrame(() => run());
    } else {
        run();
    }
}

// ========== ФОНОВАЯ ПРЕДЗАГРУЗКА КАРТИНОК ==========

let lastVendorCodesCheck = 0;
const VENDOR_CODES_CHECK_INTERVAL = 60000; // Проверяем новые товары каждые 60 секунд

async function preloadAllImages(force = false) {
    await fetchAndQueueVendorCodes(force);
}

// Периодическая проверка новых товаров
function checkForNewProducts(force = false) {
    if (!isAutoImageLoadingEnabled()) return;
    if (force || Date.now() - lastVendorCodesCheck >= VENDOR_CODES_CHECK_INTERVAL) {
        preloadAllImages(force);
    }
}

function bootstrapImageHydration() {
    scheduleHydrationTask(() => loadVisiblePendingImages(), { timeout: 250 });
    scheduleHydrationTask(() => {
        if (isAutoImageLoadingEnabled()) {
            startGlobalImagePreload(true);
        }
    }, { timeout: 1200 });
}

// Запуск предзагрузки после загрузки страницы
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapImageHydration);
} else {
    bootstrapImageHydration();
}

// Сразу применяем кэш к картинкам на странице (ко ВСЕМ картинкам с data-vendor)
function applyCachedImages(onDone) {
    const images = document.querySelectorAll('img[data-vendor]');
    if (!images.length) {
        if (typeof onDone === 'function') onDone();
        return;
    }
    let applied = 0;
    processNodesIdle(images, (img) => {
        const vendorCode = img.dataset.vendor;
        if (!vendorCode) return;
        registerVendorImage(img, vendorCode);
        const cachedUrl = workingImageUrls[vendorCode];
        if (cachedUrl && img.src !== cachedUrl) {
            img.src = cachedUrl;
            img.classList.remove('pending-image');
            applied += 1;
        }
    }, {
        onDone: () => {
            if (applied > 0) {
                console.log(`[ImageCache] Применено ${applied} картинок из кэша (мгновенно)`);
            }
            if (typeof onDone === 'function') onDone();
        }
    });
}

// Обработка картинок которые загрузились но пустые (0x0 или ошибка)
function setupImageLoadHandlers(onDone) {
    const images = document.querySelectorAll('img[data-vendor]');
    if (!images.length) {
        if (typeof onDone === 'function') onDone();
        return;
    }
    processNodesIdle(images, (img) => {
        if (img.dataset.loadHandled) return;
        img.dataset.loadHandled = '1';
        img.addEventListener('load', function() {
            if (this.naturalWidth === 0 || this.naturalHeight === 0) {
                const vendorCode = this.dataset.vendor;
                if (vendorCode && !this.src.includes('no-image')) {
                    console.log(`[ImageLoader] Пустая картинка для ${vendorCode}, ищем рабочий URL`);
                    this.src = '/static/img/no-image.svg';
                    if (window.retryImage) window.retryImage(this);
                }
            }
        });
    }, {
        onDone
    });
}

// Загрузка картинок которые ещё не загружены
function loadVisiblePendingImages() {
    applyCachedImages(() => {
        setupImageLoadHandlers(() => {
            const images = document.querySelectorAll('img[data-vendor][src*="no-image"]');
            if (!images.length) return;
            let addedCount = 0;
            const loadingAllowed = isAutoImageLoadingEnabled();
            processNodesIdle(images, (img) => {
                const vendorCode = img.dataset.vendor;
                const fallbackUrl = img.dataset.fallback;
                if (!vendorCode) {
                    if (loadingAllowed && fallbackUrl && !fallbackUrl.includes('no-image')) {
                        img.src = fallbackUrl;
                        img.classList.remove('pending-image');
                    }
                    return;
                }
                registerVendorImage(img, vendorCode);
                const cachedUrl = workingImageUrls[vendorCode];
                if (cachedUrl) {
                    img.src = cachedUrl;
                    img.classList.remove('pending-image');
                    return;
                }

                if (fallbackUrl && !fallbackUrl.includes('no-image')) {
                    img.src = fallbackUrl;
                    img.classList.remove('pending-image');
                    return;
                }

                if (failedImageUrls.has(vendorCode) || !loadingAllowed) {
                    return;
                }
                const isVisible = isElementVisible(img);
                queueImage(img, vendorCode, isVisible);
                addedCount += 1;
            }, {
                onDone: () => {
                    if (addedCount > 0 && loadingAllowed) {
                        console.log(`[ImageLoader] Добавлено ${addedCount} картинок в очередь`);
                        processImageQueue();
                    }
                }
            });
        });
    });
}


// При скролле - приоритизируем видимые картинки (с троттлингом)
let scrollTimeout = null;
let lastScrollTime = 0;
window.addEventListener('scroll', () => {
    const now = Date.now();
    if (now - lastScrollTime < 200) return; // Троттлинг
    lastScrollTime = now;
    if (scrollTimeout) return;
    scrollTimeout = setTimeout(() => {
        scrollTimeout = null;
        for (let i = backgroundImageQueue.length - 1; i >= 0; i--) {
            const item = backgroundImageQueue[i];
            if (item.img && isElementVisible(item.img)) {
                backgroundImageQueue.splice(i, 1);
                priorityImageQueue.unshift(item);
            }
        }
        processImageQueue();
    }, 50);
}, { passive: true });

function formatBarcode(code) {
    if (!code || code.length < 4) return code || '';
    const base = code.slice(0, -4);
    const highlight = code.slice(-4);
    return `<span class="barcode-base">${base}</span><span class="barcode-highlight">${highlight}</span>`;
}

// ========== STATUS HELPERS ==========

const STATUS_CONFIG = {
    'GOODS_READY': { class: 'ready', label: 'Готов к выдаче', icon: '✅' },
    'GOODS_RECIEVED': { class: 'received', label: 'Получен', icon: '📦' },
    'GOODS_COURIER_RECEIVED': { class: 'courier', label: 'У курьера', icon: '🚚' },
    'GOODS_DECLINED': { class: 'declined', label: 'Отклонён', icon: '❌' },
    'GOODS_ACCEPT_CLIENT_CANCELED': { class: 'canceled', label: 'Отменён', icon: '🚫' },
    'GOODS_WITHOUT_STATUS': { class: 'onway', label: 'В пути', icon: '🚚' },
    'ON_WAY': { class: 'onway', label: 'В пути', icon: '🚚' }
};

function getStatusClass(status) {
    return STATUS_CONFIG[status]?.class || 'default';
}

function getStatusLabel(status) {
    return STATUS_CONFIG[status]?.label || status;
}

function getStatusIcon(status) {
    return STATUS_CONFIG[status]?.icon || '📦';
}

// ========== SEARCH ==========

let searchTimeout = null;

const INLINE_SEARCH_CONFIG = {
    name: {
        inputId: 'search-name-input',
        resultsId: 'search-name-results',
        minLength: 3,
        limit: 4,
        fetcher: (query) => API.get(`/search/goods?q=${encodeURIComponent(query)}&by=name`),
        transform: (data) => data.goods || [],
        renderer: renderInlineGoodsItem,
        emptyText: 'Товары не найдены'
    },
    barcode: {
        inputId: 'search-barcode-input',
        resultsId: 'search-barcode-results',
        minLength: 4,
        limit: 3,
        fetcher: (query) => API.get(`/search/goods?q=${encodeURIComponent(query)}&by=barcode`),
        transform: (data) => data.goods || [],
        renderer: renderInlineGoodsItem,
        emptyText: 'Совпадений по ШК нет'
    },
    buyers: {
        inputId: 'search-buyers-input',
        resultsId: 'search-buyers-results',
        minLength: 2,
        limit: 4,
        fetcher: (query) => API.get(`/buyers?q=${encodeURIComponent(query)}&limit=6`),
        transform: (data) => data.buyers || [],
        renderer: renderInlineBuyerItem,
        emptyText: 'Клиенты не найдены'
    },
    orders: {
        inputId: 'search-orders-input',
        resultsId: 'search-orders-results',
        minLength: 4,
        limit: 4,
        fetcher: (query) => API.get(`/delivered?q=${encodeURIComponent(query)}&limit=40`),
        transform: (data) => data.orders || [],
        renderer: renderInlineOrderItem,
        emptyText: 'Выдачи не найдены'
    }
};

function initSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        
        if (query.length < 2) {
            hideSearchResults();
            return;
        }
        
        searchTimeout = setTimeout(() => performSearch(query), 150); // Быстрее отклик
    });
    
    searchInput.addEventListener('focus', () => {
        const query = searchInput.value.trim();
        if (query.length >= 2) performSearch(query);
    });
    
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            hideSearchResults();
        }
    });
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') hideSearchResults();
    });
}

async function performSearch(query) {
    try {
        const data = await API.get(`/search?q=${encodeURIComponent(query)}`);
        displaySearchResults(data);
    } catch (err) {
        console.error('Search error:', err);
    }
}

function displaySearchResults(data) {
    let resultsDiv = document.getElementById('search-results');
    if (!resultsDiv) {
        resultsDiv = document.createElement('div');
        resultsDiv.id = 'search-results';
        resultsDiv.className = 'search-results';
        document.querySelector('.search-container').appendChild(resultsDiv);
    }
    
    resultsDiv.innerHTML = '';
    let hasResults = false;
    
    if (data.goods?.length > 0) {
        resultsDiv.appendChild(createResultSection('Товары в ПВЗ', data.goods, renderGoodsResult));
        hasResults = true;
    }
    
    if (data.buyers?.length > 0) {
        resultsDiv.appendChild(createResultSection('Клиенты', data.buyers, renderBuyerResult));
        hasResults = true;
    }
    
    if (data.delivered?.length > 0) {
        resultsDiv.appendChild(createResultSection('История выдачи', data.delivered, renderDeliveredResult));
        hasResults = true;
    }
    
    if (!hasResults) {
        resultsDiv.innerHTML = `
            <div class="search-empty">
                <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>
                </svg>
                <p>Ничего не найдено</p>
            </div>
        `;
    }
    
    resultsDiv.style.display = 'block';
}

function hideSearchResults() {
    const resultsDiv = document.getElementById('search-results');
    if (resultsDiv) resultsDiv.style.display = 'none';
}

function createResultSection(title, items, renderFn) {
    const section = document.createElement('div');
    section.className = 'search-section';
    section.innerHTML = `<div class="search-section-title">${title}</div>`;
    items.forEach(item => section.appendChild(renderFn(item)));
    return section;
}

function renderGoodsResult(goods) {
    const div = document.createElement('div');
    div.className = 'search-result-item';
    div.innerHTML = `
        <img src="${goods.image_url || '/static/img/no-image.svg'}" 
             onerror="this.src='/static/img/no-image.svg'" alt="">
        <div class="search-result-info">
            <div class="search-result-title">${goods.info?.brand || ''} ${goods.info?.name || 'Товар'}</div>
            <div class="search-result-meta">
                <span class="goods-status status-${getStatusClass(goods.status)}">${getStatusLabel(goods.status)}</span>
                ШК: ${goods.scanned_code} ${goods.cell ? `| Яч: <strong>${goods.cell}</strong>` : ''}
            </div>
        </div>
    `;
    div.onclick = () => openGoodsModal(goods);
    return div;
}

function renderBuyerResult(buyer) {
    const div = document.createElement('div');
    div.className = 'search-result-item';
    div.innerHTML = `
        <div class="buyer-avatar-small">${buyer.display_name?.charAt(0) || '?'}</div>
        <div class="search-result-info">
            <div class="search-result-title">${buyer.display_name || 'Клиент'}</div>
            <div class="search-result-meta">${formatPhonePlain(buyer.mobile)} ${buyer.cell ? `| Яч: <strong>${buyer.cell}</strong>` : ''}</div>
        </div>
    `;
    div.onclick = () => window.location.href = `/buyer/${buyer.user_sid}`;
    return div;
}

function renderDeliveredResult(item) {
    const div = document.createElement('div');
    div.className = 'search-result-item';
    const deliveredAt = formatDate(item.delivery_timestamp || item.timestamp, { verbose: true, withSeconds: true });
    div.innerHTML = `
        <div class="search-result-icon">📦</div>
        <div class="search-result-info">
            <div class="search-result-title">ШК: ${item.scanned_code || item.order_id}</div>
            <div class="search-result-meta">${deliveredAt ? `Выдан ${deliveredAt}` : ''}</div>
        </div>
    `;
    div.onclick = () => openOrderByGoodsUid(item.goods_uid || item.goodsUid);
    return div;
}

function initInlineSearches() {
    document.querySelectorAll('.search-inline-results').forEach(container => {
        const hint = container.dataset.empty || 'Введите запрос';
        container.textContent = hint;
    });
    Object.entries(INLINE_SEARCH_CONFIG).forEach(([action, config]) => {
        const input = document.getElementById(config.inputId);
        const button = document.querySelector(`[data-search-action="${action}"]`);
        if (!input || !button) return;
        const handler = () => runInlineSearch(action);
        button.addEventListener('click', handler);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handler();
            }
        });
    });
}

async function runInlineSearch(action) {
    const config = INLINE_SEARCH_CONFIG[action];
    if (!config) return;
    const input = document.getElementById(config.inputId);
    const container = document.getElementById(config.resultsId);
    if (!input || !container) return;
    const query = input.value.trim();
    if (query.length < (config.minLength || 2)) {
        setInlineResultsMessage(container, config.tooShortText || `Введите минимум ${config.minLength || 2} символа`);
        return;
    }
    setInlineResultsMessage(container, 'Ищем...');
    try {
        const data = await config.fetcher(query);
        const items = (config.transform ? config.transform(data) : data) || [];
        renderInlineResults(
            container,
            items,
            config.renderer,
            config.limit,
            config.emptyText || 'Ничего не найдено'
        );
    } catch (err) {
        console.error('Inline search error:', err);
        setInlineResultsMessage(container, 'Ошибка поиска');
    }
}

function setInlineResultsMessage(container, message) {
    if (container) {
        container.textContent = message;
    }
}

function renderInlineResults(container, items, renderer, limit = 4, emptyText = 'Нет данных') {
    if (!container) return;
    if (!items || items.length === 0) {
        container.textContent = emptyText;
        return;
    }
    container.innerHTML = '';
    items.slice(0, limit).forEach(item => container.appendChild(renderer(item)));
}

function renderInlineGoodsItem(goods) {
    const div = document.createElement('div');
    div.className = 'search-inline-item';
    const brand = goods.info?.brand || 'Товар';
    const name = goods.info?.name || '';
    const cell = goods.cell ? `Яч. ${goods.cell}` : 'Без ячейки';
    const adultBadge = goods.info?.adult ? '<span class="goods-tag adult" style="font-size: 10px; padding: 1px 4px; margin-left: 4px;">18+</span>' : '';
    div.innerHTML = `
        <div>
            <strong>${brand}</strong>${adultBadge}
            <div class="search-inline-meta">${name}</div>
        </div>
        <div class="search-inline-meta">${cell}</div>
    `;
    div.addEventListener('click', () => openGoodsModal(goods));
    return div;
}

function renderInlineBuyerItem(buyer) {
    const div = document.createElement('div');
    div.className = 'search-inline-item';
    const phone = buyer.mobile ? formatPhonePlain(buyer.mobile) : '';
    const cell = buyer.cell ? `Яч. ${buyer.cell}` : '';
    div.innerHTML = `
        <div>
            <strong>${buyer.display_name || 'Клиент'}</strong>
            <div class="search-inline-meta">${phone}</div>
        </div>
        <div class="search-inline-meta">${cell}</div>
    `;
    div.addEventListener('click', () => {
        if (buyer.user_sid) {
            window.location.href = `/buyer/${buyer.user_sid}`;
        }
    });
    return div;
}

function renderInlineOrderItem(order) {
    const div = document.createElement('div');
    div.className = 'search-inline-item has-thumb';
    const barcode = order.scanned_code || order.order_id || '—';
    const buyer = order.buyer_name || 'Клиент';
    const date = formatDate(order.delivery_timestamp || order.timestamp, { verbose: true, withSeconds: true });
    const product = order.info?.name || '';
    const vendorCode = order.vendor_code ? String(order.vendor_code) : '';
    const fallbackUrl = order.image_url || '';
    const imageSrc = getInitialImageSrc(vendorCode, fallbackUrl);
    div.innerHTML = `
        <div class="search-inline-thumb">
            <img src="${imageSrc}" alt="Товар" loading="lazy" data-vendor="${vendorCode}" data-fallback="${fallbackUrl}"
                 onerror="if(window.retryImage) window.retryImage(this); else this.src='/static/img/no-image.svg';">
        </div>
        <div class="search-inline-content">
            <div>
                <strong>ШК ${barcode}</strong>
                <div class="search-inline-meta">${buyer}${date ? ` · Выдан ${date}` : ''}</div>
            </div>
            <div class="search-inline-meta search-inline-product">${product}</div>
        </div>
    `;
    hydrateVendorImages(div, '.search-inline-thumb img[data-vendor]', true, { defer: true });
    div.addEventListener('click', () => openOrderByGoodsUid(order.goods_uid || order.goodsUid));
    return div;
}

// ========== MODALS ==========

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    document.body.style.overflow = '';
}

// ========== QR MODAL ==========

function openQRModal(encodedCode, scannedCode) {
    // Создаём модальное окно если не существует
    let modal = document.getElementById('qr-modal');
    if (!modal) {
        modal = createQRModal();
        document.body.appendChild(modal);
    }
    
    // Заполняем данные
    const qrImage = modal.querySelector('.qr-modal-image');
    qrImage.src = `/api/qr/${encodeURIComponent(encodedCode)}`;
    
    // Форматируем штрих-код с увеличенными последними 4 цифрами
    const barcodeEl = modal.querySelector('.qr-modal-barcode');
    if (scannedCode) {
        const base = scannedCode.slice(0, -4);
        const highlight = scannedCode.slice(-4);
        barcodeEl.innerHTML = `
            <span class="barcode-base">${base}</span>
            <span class="barcode-highlight">${highlight}</span>
        `;
    }
    
    // Сохраняем код для скачивания
    modal.dataset.encodedCode = encodedCode;
    modal.dataset.scannedCode = scannedCode;
    
    openModal('qr-modal');
}

function createQRModal() {
    const modal = document.createElement('div');
    modal.id = 'qr-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal qr-modal-content">
            <div class="modal-header">
                <h3 class="modal-title">QR-код товара</h3>
                <button class="modal-close" onclick="closeModal('qr-modal')">
                    <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="qr-modal-container">
                    <div class="qr-modal-qr-wrapper">
                        <img class="qr-modal-image" src="" alt="QR Code">
                    </div>
                    <div class="qr-modal-barcode"></div>
                    <div class="qr-modal-actions">
                        <button class="btn btn-primary" onclick="saveQRCode()">
                            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                            </svg>
                            Сохранить QR
                        </button>
                        <button class="btn btn-secondary" onclick="copyBarcodeFromModal()">
                            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                            </svg>
                            Копировать ШК
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal('qr-modal');
    });
    
    return modal;
}

async function saveQRCode() {
    const modal = document.getElementById('qr-modal');
    const encodedCode = modal?.dataset.encodedCode;
    const scannedCode = modal?.dataset.scannedCode || 'qr-code';
    
    if (!encodedCode) {
        Toast.error('Код не найден');
        return;
    }
    
    try {
        const response = await fetch(`/api/qr/${encodeURIComponent(encodedCode)}?download=true`);
        const blob = await response.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `qr_${scannedCode}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        Toast.success('QR-код сохранён');
    } catch (err) {
        Toast.error('Ошибка сохранения');
    }
}

function copyBarcodeFromModal() {
    const modal = document.getElementById('qr-modal');
    const scannedCode = modal?.dataset.scannedCode;
    if (scannedCode) {
        copyToClipboard(scannedCode);
    }
}

// ========== GOODS MODAL ==========

const GOODS_NOTE_STORAGE_PREFIX = 'goods_note_';
let goodsNoteSaveTimeout = null;

function getGoodsNoteKey(goods) {
    if (!goods) return '';
    return goods.item_uid || goods.scanned_code || goods.sticker_code || goods.barcode || '';
}

function loadGoodsNoteValue(noteKey) {
    if (!noteKey) return '';
    try {
        return localStorage.getItem(GOODS_NOTE_STORAGE_PREFIX + noteKey) || '';
    } catch (err) {
        console.warn('goods-note load failed', err);
        return '';
    }
}

function saveGoodsNoteValue(noteKey, value) {
    if (!noteKey) return;
    const storageKey = GOODS_NOTE_STORAGE_PREFIX + noteKey;
    try {
        if (value && value.trim()) {
            localStorage.setItem(storageKey, value);
        } else {
            localStorage.removeItem(storageKey);
        }
    } catch (err) {
        console.warn('goods-note save failed', err);
    }
}

function hydrateGoodsNote(modal, goods) {
    if (goodsNoteSaveTimeout) {
        clearTimeout(goodsNoteSaveTimeout);
        goodsNoteSaveTimeout = null;
    }
    const textarea = modal.querySelector('.goods-modal-note-input');
    const statusEl = modal.querySelector('.goods-modal-note-status');
    const clearBtn = modal.querySelector('.goods-modal-note-actions button');
    if (!textarea || !statusEl) return;
    const noteKey = getGoodsNoteKey(goods);
    modal.dataset.noteKey = noteKey || '';
    if (!noteKey) {
        textarea.value = '';
        textarea.disabled = true;
        if (clearBtn) clearBtn.disabled = true;
        statusEl.textContent = 'Недоступно';
        return;
    }
    textarea.disabled = false;
    if (clearBtn) clearBtn.disabled = false;
    const currentValue = loadGoodsNoteValue(noteKey);
    textarea.value = currentValue;
    statusEl.textContent = currentValue.trim() ? 'Автосохранение' : 'Пусто';
}

function handleGoodsNoteInput(event) {
    const modal = document.getElementById('goods-modal');
    if (!modal) return;
    const noteKey = modal.dataset.noteKey;
    if (!noteKey) return;
    const statusEl = modal.querySelector('.goods-modal-note-status');
    if (statusEl) statusEl.textContent = 'Сохранение...';
    if (goodsNoteSaveTimeout) {
        clearTimeout(goodsNoteSaveTimeout);
    }
    const value = event.target.value;
    goodsNoteSaveTimeout = setTimeout(() => {
        saveGoodsNoteValue(noteKey, value);
        if (statusEl) {
            statusEl.textContent = value.trim() ? 'Сохранено' : 'Пусто';
            setTimeout(() => {
                if (modal.dataset.noteKey === noteKey) {
                    statusEl.textContent = 'Автосохранение';
                }
            }, 2000);
        }
    }, 500);
}

function clearGoodsNote() {
    const modal = document.getElementById('goods-modal');
    if (!modal) return;
    const noteKey = modal.dataset.noteKey;
    const textarea = modal.querySelector('.goods-modal-note-input');
    const statusEl = modal.querySelector('.goods-modal-note-status');
    if (!noteKey || !textarea) return;
    if (goodsNoteSaveTimeout) {
        clearTimeout(goodsNoteSaveTimeout);
        goodsNoteSaveTimeout = null;
    }
    textarea.value = '';
    saveGoodsNoteValue(noteKey, '');
    if (statusEl) statusEl.textContent = 'Пусто';
    Toast.success('Мини заметка очищена');
}

function openGoodsModal(goods) {
    let modal = document.getElementById('goods-modal');
    if (!modal) {
        modal = createGoodsModal();
        document.body.appendChild(modal);
    }
    
    // Сохраняем vendor_code для кнопки обновления
    const vendorCode = goods.vendor_code?.toString();
    currentModalVendorCode = vendorCode;
    
    // Скрываем кнопку "Весь заказ" по умолчанию (она показывается только для выданных товаров)
    const orderBtn = modal.querySelector('[data-field="order-link"]');
    if (orderBtn) {
        orderBtn.style.display = 'none';
        orderBtn.classList.remove('loading');
    }
    currentDeliveredGoodsUid = null;
    
    // Заполняем данные
    // Проверяем кэш картинок - если нашли рабочий URL, используем его
    let imageUrl = '/static/img/no-image.svg';
    
    // Приоритет: кэш > image_url из данных > заглушка
    if (vendorCode && workingImageUrls[vendorCode]) {
        imageUrl = workingImageUrls[vendorCode];
    } else if (goods.image_url && !goods.image_url.includes('no-image')) {
        imageUrl = goods.image_url;
    }
    
    const modalImage = modal.querySelector('.goods-modal-image');
    modalImage.src = imageUrl;
    modalImage.dataset.vendor = vendorCode || '';
    modalImage.onerror = function() { 
        if(window.retryImage) window.retryImage(this); 
        else this.src='/static/img/no-image.svg'; 
    };
    
    // Если картинка не в кэше - загрузим с высоким приоритетом
    if (vendorCode && !workingImageUrls[vendorCode] && !failedImageUrls.has(vendorCode)) {
        queueImage(modalImage, vendorCode, true);
        processImageQueue();
    }
    
    modal.querySelector('.goods-modal-brand').textContent = goods.info?.brand || 'Бренд';
    modal.querySelector('.goods-modal-name').textContent = goods.info?.name || 'Товар';
    
    // Статус
    const statusEl = modal.querySelector('.goods-modal-status');
    if (statusEl) {
        statusEl.textContent = getStatusLabel(goods.status);
        statusEl.className = `goods-status goods-modal-status status-${getStatusClass(goods.status)}`;
    }

    const receivedEl = modal.querySelector('.goods-modal-received');
    if (receivedEl) {
        if (goods.status === 'GOODS_RECIEVED') {
            const receivedTimestamp = goods.status_updated || goods.delivery_timestamp || goods.received_at || goods.updated_at;
            const formattedReceived = receivedTimestamp ? formatDate(receivedTimestamp) : '';
            if (formattedReceived) {
                receivedEl.textContent = `Выдан ${formattedReceived}`;
                receivedEl.style.display = 'block';
            } else {
                receivedEl.style.display = 'none';
            }
        } else {
            receivedEl.style.display = 'none';
        }
    }
    
    // Детали
    const setField = (field, value, { html = false } = {}) => {
        const el = modal.querySelector(`[data-field="${field}"]`);
        if (!el) return;
        if (!value) {
            if (html) {
                el.innerHTML = '-';
            } else {
                el.textContent = '-';
            }
            return;
        }
        if (html) {
            el.innerHTML = value;
        } else {
            el.textContent = value;
        }
    };
    
    setField('cell', goods.cell);
    const barcodeValue = goods.scanned_code || goods.sticker_code;
    setField('barcode', barcodeValue ? formatBarcode(barcodeValue) : null, { html: true });
    setField('vendor', goods.vendor_code);
    setField('category', goods.info?.subject_name);
    setField('color', goods.info?.color);
    setField('barcode_raw', goods.barcode);
    
    // Ссылка на клиента и номер телефона
    const buyerLink = modal.querySelector('[data-field="buyer-link"]');
    const buyerDetail = modal.querySelector('.buyer-detail');
    const buyerMobileEl = modal.querySelector('[data-field="buyer_mobile"]');
    const setBuyerMobile = (phone) => {
        if (!buyerMobileEl) return;
        const formatted = formatPhone(phone);
        if (formatted) {
            buyerMobileEl.innerHTML = formatted;
        } else {
            buyerMobileEl.textContent = '-';
        }
    };
    
    if (goods.buyer_sid) {
        if (buyerLink) {
            buyerLink.href = `/buyer/${goods.buyer_sid}`;
            buyerLink.style.display = 'inline-flex';
        }
        if (buyerDetail) {
            buyerDetail.style.display = 'block';
            // Если есть номер в данных товара
            if (goods.buyer_mobile) {
                setBuyerMobile(goods.buyer_mobile);
            } else if (buyerMobileEl) {
                // Загружаем данные покупателя
                buyerMobileEl.textContent = 'Загрузка...';
                fetch(`/api/buyer/${goods.buyer_sid}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.mobile) {
                            setBuyerMobile(data.mobile);
                        } else {
                            buyerMobileEl.textContent = '-';
                        }
                    })
                    .catch(() => buyerMobileEl.textContent = '-');
            }
        }
    } else {
        if (buyerLink) buyerLink.style.display = 'none';
        if (buyerDetail) buyerDetail.style.display = 'none';
    }
    
    // Ссылка на WB
    const wbLink = modal.querySelector('[data-field="wb-link"]');
    if (wbLink && goods.vendor_code) {
        wbLink.href = `https://www.wildberries.ru/catalog/${goods.vendor_code}/detail.aspx`;
        wbLink.style.display = 'inline-flex';
    } else if (wbLink) {
        wbLink.style.display = 'none';
    }
    
    // Цена со скидкой и без
    const priceWithSale = goods.price_with_sale || goods.price || 0;
    const priceOriginal = goods.price || 0;
    const hasDiscount = priceOriginal > priceWithSale && priceWithSale > 0;
    const priceEl = modal.querySelector('[data-field="price"]');
    if (priceEl) {
        if (hasDiscount) {
            priceEl.innerHTML = `<span class="goods-price-original">${formatPrice(priceOriginal)}</span> <span class="goods-price-sale">${formatPrice(priceWithSale)}</span>`;
        } else {
            priceEl.textContent = formatPrice(priceWithSale);
        }
    }
    
    // Теги
    const tagsContainer = modal.querySelector('.goods-modal-tags');
    if (tagsContainer) {
        tagsContainer.innerHTML = '';
        if (goods.info?.adult) {
            tagsContainer.innerHTML += '<span class="goods-tag adult">18+</span>';
        }
        if (goods.info?.no_return) {
            tagsContainer.innerHTML += '<span class="goods-tag no-return">Без возврата</span>';
        }
        if (goods.priority_order) {
            tagsContainer.innerHTML += '<span class="goods-tag priority">Приоритет</span>';
        }
        if (goods.is_paid === 1 || goods.is_paid === true) {
            tagsContainer.innerHTML += '<span class="goods-tag paid">Оплачен</span>';
        }
    }
    
    // Кнопка "Весь заказ"
    const deliveredUid = goods.goods_uid || goods.goodsUid || (goods.status === 'GOODS_RECIEVED' ? goods.item_uid : null);
    if (orderBtn && deliveredUid) {
        currentDeliveredGoodsUid = deliveredUid;
        orderBtn.style.display = 'inline-flex';
    }

    // QR секция
    const qrSection = modal.querySelector('.goods-modal-qr-section');
    if (qrSection) {
        const qrPreviewWrapper = qrSection.querySelector('.qr-preview-wrapper');
        const qrPreview = qrSection.querySelector('.qr-preview');
        const qrInfo = qrSection.querySelector('.qr-info');
        const qrMessage = qrSection.querySelector('.qr-missing-message');
        const barcodeDisplay = qrSection.querySelector('.qr-barcode-display');
        const hasEncodedCode = Boolean(goods.encoded_scanned_code);

        qrSection.style.display = 'flex';
        qrSection.classList.toggle('qr-unavailable', !hasEncodedCode);
        qrSection.dataset.encodedCode = hasEncodedCode ? goods.encoded_scanned_code : '';
        qrSection.dataset.scannedCode = goods.scanned_code || '';

        if (hasEncodedCode) {
            if (qrPreview) {
                qrPreview.src = `/api/qr/${encodeURIComponent(goods.encoded_scanned_code)}?size=80`;
            }
            if (qrPreviewWrapper) {
                qrPreviewWrapper.style.display = '';
            }
            if (qrInfo) {
                qrInfo.style.display = '';
            }
            if (qrMessage) {
                qrMessage.style.display = 'none';
                qrMessage.textContent = '';
            }
            if (barcodeDisplay && goods.scanned_code) {
                const base = goods.scanned_code.slice(0, -4);
                const highlight = goods.scanned_code.slice(-4);
                barcodeDisplay.innerHTML = `${base}<span class="highlight">${highlight}</span>`;
            } else if (barcodeDisplay) {
                barcodeDisplay.innerHTML = '';
            }
        } else {
            if (qrPreviewWrapper) {
                qrPreviewWrapper.style.display = 'none';
            }
            if (qrInfo) {
                qrInfo.style.display = 'none';
            }
            if (qrMessage) {
                qrMessage.textContent = 'ШК не сканировался на ПВЗ или невозможно сгенерировать QR этого товара';
                qrMessage.style.display = 'block';
            }
            if (barcodeDisplay) {
                barcodeDisplay.innerHTML = '';
            }
        }
    }
    
    // Сохраняем данные для копирования
    modal.dataset.scannedCode = goods.scanned_code;
    hydrateGoodsNote(modal, goods);
    
    openModal('goods-modal');
}

function openProfileGoodsCard(node) {
    if (!node) return;
    try {
        const payload = node.dataset.good;
        if (!payload) return;
        const parsed = JSON.parse(payload);
        openGoodsModal(parsed);
    } catch (error) {
        console.error('Failed to open goods card modal', error);
    }
}

function createGoodsModal() {
    const modal = document.createElement('div');
    modal.id = 'goods-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal modal-goods">
            <div class="modal-header">
                <h3 class="modal-title">Информация о товаре</h3>
                <button class="modal-close" onclick="closeModal('goods-modal')">
                    <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="goods-modal-layout">
                    <div class="goods-modal-media">
                        <div class="goods-modal-image-wrapper">
                            <img class="goods-modal-image" src="/static/img/no-image.svg" alt="">
                            <button class="goods-modal-image-refresh" onclick="refreshModalImage()" title="Загрузить картинку">
                                <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                            </button>
                        </div>
                        <div class="goods-modal-actions">
                            <a class="btn btn-secondary btn-buyer-link" href="#" data-field="buyer-link">
                                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                                </svg>
                                Профиль клиента
                            </a>
                            <a class="btn btn-primary btn-wb-link" href="#" target="_blank" data-field="wb-link">
                                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                </svg>
                                Открыть на WB
                            </a>
                            <button class="btn btn-secondary btn-order-link" data-field="order-link" style="display:none" onclick="showFullOrder()">
                                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                                </svg>
                                Весь заказ
                            </button>
                        </div>
                    </div>
                    <div class="goods-modal-info">

                        <div class="goods-modal-brand">Бренд</div>
                        <div class="goods-modal-name">Название товара</div>
                        <div class="goods-modal-tags"></div>
                        <span class="goods-status goods-modal-status">Статус</span>
                        <div class="goods-modal-received" style="display:none"></div>

                        <div class="goods-modal-details">
                            <div class="goods-modal-detail">
                                <div class="goods-modal-detail-label">Ячейка</div>
                                <div class="goods-modal-detail-value cell" data-field="cell">-</div>
                            </div>
                            <div class="goods-modal-detail">
                                <div class="goods-modal-detail-label">Цена</div>
                                <div class="goods-modal-detail-value price" data-field="price">0 ₽</div>
                            </div>
                            <div class="goods-modal-detail clickable" onclick="copyModalBarcode(this)">
                                <div class="goods-modal-detail-label">ШК</div>
                                <div class="goods-modal-detail-value barcode" data-field="barcode">-</div>
                            </div>
                            <div class="goods-modal-detail">
                                <div class="goods-modal-detail-label">Артикул</div>
                                <div class="goods-modal-detail-value" data-field="vendor">-</div>
                            </div>
                            <div class="goods-modal-detail">
                                <div class="goods-modal-detail-label">Категория</div>
                                <div class="goods-modal-detail-value" data-field="category">-</div>
                            </div>
                            <div class="goods-modal-detail">
                                <div class="goods-modal-detail-label">Цвет</div>
                                <div class="goods-modal-detail-value" data-field="color">-</div>
                            </div>
                            <div class="goods-modal-detail">
                                <div class="goods-modal-detail-label">Баркод</div>
                                <div class="goods-modal-detail-value" data-field="barcode_raw">-</div>
                            </div>
                            <div class="goods-modal-detail buyer-detail" style="display:none">
                                <div class="goods-modal-detail-label">Клиент</div>
                                <div class="goods-modal-detail-value" data-field="buyer_mobile">-</div>
                            </div>
                        </div>
                        <div class="goods-modal-note">
                            <div class="goods-modal-note-header">
                                <div class="goods-modal-note-title">Мини заметка</div>
                                <span class="goods-modal-note-status">Пусто</span>
                            </div>
                            <textarea class="goods-modal-note-input" placeholder="Запишите сюда всё важное о товаре..." rows="3"></textarea>
                            <div class="goods-modal-note-actions">
                                <button class="btn btn-sm btn-secondary" type="button" onclick="clearGoodsNote()">Очистить</button>
                            </div>
                        </div>
                        
                    </div>
                </div>
                
                <div class="goods-modal-qr-section" style="display:none">
                    <div class="qr-preview-wrapper">
                        <img class="qr-preview" src="" alt="QR">
                    </div>
                    <div class="qr-info">
                        <div class="qr-barcode-display"></div>
                        <div class="qr-actions">
                            <button class="btn btn-sm btn-primary" onclick="openQRFromGoodsModal()">
                                Открыть QR
                            </button>
                        </div>
                    </div>
                    <div class="qr-missing-message" style="display:none"></div>
                </div>
            </div>
        </div>
    `;
    const noteInput = modal.querySelector('.goods-modal-note-input');
    if (noteInput) {
        noteInput.addEventListener('input', handleGoodsNoteInput);
    }
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal('goods-modal');
    });
    
    return modal;
}

function copyModalBarcode(element) {
    const modal = document.getElementById('goods-modal');
    const code = modal?.dataset.scannedCode;
    if (code) {
        copyToClipboard(code, element.querySelector('.goods-modal-detail-value'));
    }
}

function openQRFromGoodsModal() {
    const section = document.querySelector('.goods-modal-qr-section');
    if (section && section.dataset.encodedCode) {
        openQRModal(section.dataset.encodedCode, section.dataset.scannedCode);
    }
}

// ========== NAVIGATION ==========

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const currentPath = window.location.pathname;
    const currentSearch = window.location.search;
    const isBuyersPage = currentPath === '/buyers';
    const isBuyerProfile = currentPath.startsWith('/buyer/');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (!href || href === '#' || href.startsWith('javascript:')) {
            item.classList.remove('active');
            return;
        }
        if (!href) return;
        const url = new URL(href, window.location.origin);
        const itemPath = url.pathname;
        const itemSearch = url.search;
        const baseMatch = itemPath === currentPath && (!itemSearch || itemSearch === currentSearch);
        const isClientsSection = itemPath === '/buyers' && (isBuyersPage || isBuyerProfile);
        let shouldActivate = baseMatch;

        if (!shouldActivate && isClientsSection) {
            if (!itemSearch) {
                shouldActivate = !currentSearch || !currentSearch.includes('view=try-on') || isBuyerProfile;
            } else if (itemSearch.includes('view=try-on')) {
                shouldActivate = currentSearch.includes('view=try-on');
            }
        }

        if (!shouldActivate && itemPath === '/' && currentPath === '/') {
            shouldActivate = true;
        }

        if (shouldActivate) {
            item.classList.add('active');
        }
    });
}

// ========== GOODS LOADING ==========

async function loadGoods(container, type = 'pickup', page = 1) {
    const limit = 20;
    const offset = (page - 1) * limit;
    
    try {
        showLoading(container);
        
        const endpoint = type === 'pickup' ? '/goods/pickup' : '/goods/on-way';
        const data = await API.get(`${endpoint}?limit=${limit}&offset=${offset}`);
        
        renderGoodsGrid(container, data.goods);
    } catch (err) {
        console.error('Load goods error:', err);
        showError(container, 'Ошибка загрузки товаров');
    }
}

function renderGoodsGrid(container, goods) {
    if (!goods || goods.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                    </svg>
                </div>
                <div class="empty-state-title">Нет товаров</div>
                <div class="empty-state-text">Товары появятся здесь после поступления</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `<div class="goods-grid">${goods.map(g => createGoodsCard(g)).join('')}</div>`;
    
    // Загружаем картинки которые не в кэше
    requestAnimationFrame(() => {
        loadPendingImages(container);
    });
}

// Загрузка картинок которые нужно подгрузить (с приоритетом для видимых)
function loadPendingImages(container) {
    const images = container.querySelectorAll('img[data-needs-load="1"]');
    images.forEach(img => {
        const vendorCode = img.dataset.vendor;
        if (vendorCode) {
            const isVisible = isElementVisible(img);
            queueImage(img, vendorCode, isVisible); // true = высокий приоритет для видимых
        }
        img.removeAttribute('data-needs-load');
    });
    processImageQueue();
}

function createGoodsCard(g) {
    const goodsJson = JSON.stringify(g).replace(/'/g, "&#39;").replace(/"/g, "&quot;");
    const isPaid = g.is_paid === 1 || g.is_paid === true;
    
    // Показываем обе цены: со скидкой и без
    const priceWithSale = g.price_with_sale || g.price || 0;
    const priceOriginal = g.price || 0;
    const hasDiscount = priceOriginal > priceWithSale && priceWithSale > 0;
    
    // Используем кэшированный URL если есть (приводим к строке!)
    const vendorCode = g.vendor_code?.toString();
    let imageUrl = '/static/img/no-image.svg'; // По умолчанию заглушка
    let needsLoad = false;
    
    if (vendorCode && workingImageUrls[vendorCode]) {
        // Есть в кэше - используем сразу
        imageUrl = workingImageUrls[vendorCode];
    } else if (vendorCode && !failedImageUrls.has(vendorCode)) {
        // Нет в кэше и не в списке неудачных - загрузим в фоне
        needsLoad = true;
    }
    
    return `
        <div class="goods-card" onclick='openGoodsModal(${JSON.stringify(g).replace(/'/g, "&#39;")})'>
            <div class="goods-card-image">
                <img src="${imageUrl}" 
                     onerror="if(window.retryImage) window.retryImage(this); else this.src='/static/img/no-image.svg';" alt="" loading="lazy" 
                     data-vendor="${vendorCode || ''}" ${needsLoad ? 'data-needs-load="1"' : ''}>
                <div class="goods-card-status">
                    <span class="goods-status status-${getStatusClass(g.status)}">${getStatusLabel(g.status)}</span>
                </div>
                ${g.cell ? `<div class="goods-card-cell">🗄️ ${g.cell}</div>` : ''}
            </div>
            <div class="goods-card-body">
                <div class="goods-brand">${g.info?.brand || ''}</div>
                <div class="goods-name">${g.info?.name || 'Товар'}</div>
                
                <div class="goods-info-row">
                    ${g.info?.adult ? '<span class="goods-tag adult">18+</span>' : ''}
                    ${g.info?.no_return ? '<span class="goods-tag no-return">Без возврата</span>' : ''}
                    ${g.priority_order ? '<span class="goods-tag priority">Приоритет</span>' : ''}
                </div>
                
                <div class="goods-card-footer">
                    <div class="goods-barcodes">
                        <div class="goods-barcode" onclick="event.stopPropagation(); copyToClipboard('${g.scanned_code}', this)" title="ШК сканированный">
                            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                            </svg>
                            ${g.scanned_code}
                        </div>
                        ${g.barcode ? `
                        <div class="goods-barcode barcode-ean" onclick="event.stopPropagation(); copyToClipboard('${g.barcode}', this)" title="Штрихкод EAN">
                            📊 ${g.barcode}
                        </div>
                        ` : ''}
                    </div>
                    <div class="goods-price-block">
                        ${hasDiscount ? `
                            <div class="goods-price-original">${formatPrice(priceOriginal)}</div>
                            <div class="goods-price goods-price-sale">${formatPrice(priceWithSale)}</div>
                        ` : `
                            <div class="goods-price">${formatPrice(priceWithSale)}</div>
                        `}
                        <span class="goods-payment-badge ${isPaid ? 'paid' : 'unpaid'}">
                            ${isPaid ? 'Оплачен' : 'К оплате'}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// ========== BUYERS LOADING ==========

async function loadBuyers(container, page = 1, search = '') {
    const limit = 30;
    const offset = (page - 1) * limit;
    
    try {
        showLoading(container);
        
        let endpoint = `/buyers?limit=${limit}&offset=${offset}`;
        if (search) endpoint += `&q=${encodeURIComponent(search)}`;
        
        const data = await API.get(endpoint);
        renderBuyersList(container, data.buyers);
    } catch (err) {
        console.error('Load buyers error:', err);
        showError(container, 'Ошибка загрузки клиентов');
    }
}

function renderBuyersList(container, buyers) {
    if (!buyers || buyers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                    </svg>
                </div>
                <div class="empty-state-title">Клиенты не найдены</div>
                <div class="empty-state-text">Попробуйте изменить параметры поиска</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `<div class="buyers-grid">${buyers.map(createBuyerCard).join('')}</div>`;
}

function createBuyerCard(b) {
    return `
        <a href="/buyer/${b.user_sid}" class="buyer-card">
            <div class="buyer-avatar">
                ${b.custom_photo_path 
                    ? `<img src="/api/buyer-photo/${b.user_sid}" onerror="this.remove()" alt="">` 
                    : (b.display_name?.charAt(0)?.toUpperCase() || '?')}
            </div>
            <div class="buyer-info">
                <div class="buyer-name">${b.display_name || 'Клиент'}</div>
                <div class="buyer-phone">${formatPhone(b.mobile)}</div>
            </div>
            ${b.cell ? `
                <div class="buyer-cell">
                    <div class="buyer-cell-number">${b.cell}</div>
                    <div class="buyer-cell-label">Ячейка</div>
                </div>
            ` : ''}
        </a>
    `;
}

// ========== SURPLUS ==========

async function loadSurplus(container) {
    try {
        showLoading(container);
        const data = await API.get('/surplus');
        renderSurplusGrid(container, data.surplus);
    } catch (err) {
        console.error('Load surplus error:', err);
        showError(container, 'Ошибка загрузки излишков');
    }
}

function renderSurplusGrid(container, items) {
    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div class="empty-state-title">Излишков нет</div>
                <div class="empty-state-text">Все товары учтены правильно</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="section-header">
            <h3 class="section-title">Излишки (${items.length})</h3>
            <button class="btn btn-danger" onclick="clearAllSurplus()">
                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
                Очистить все
            </button>
        </div>
        <div class="goods-grid">${items.map(createSurplusCard).join('')}</div>
    `;
}

function createSurplusCard(item) {
    return `
        <div class="goods-card surplus-card">
            <div class="goods-card-body">
                <div class="goods-brand">Излишек</div>
                <div class="goods-barcode" onclick="copyToClipboard('${item.scanned_code || item.sticker_code}', this)">
                    ${item.scanned_code || item.sticker_code}
                </div>
                <div class="surplus-meta">
                    <span>Добавлен: ${formatDate(item.created_at)}</span>
                </div>
            </div>
        </div>
    `;
}

async function clearAllSurplus() {
    if (!confirm('Удалить все записи об излишках?')) return;
    
    try {
        await API.delete('/surplus');
        Toast.success('Излишки очищены');
        
        const container = document.getElementById('surplus-container');
        if (container) loadSurplus(container);
    } catch (err) {
        Toast.error('Ошибка очистки');
    }
}

// ========== DELIVERED ORDERS ==========

async function loadDelivered(container, search = '') {
    try {
        showLoading(container);
        
        let endpoint = '/delivered';
        if (search) endpoint += `?q=${encodeURIComponent(search)}`;
        
        const data = await API.get(endpoint);
        renderDeliveredList(container, data.orders);
    } catch (err) {
        console.error('Load delivered error:', err);
        showError(container, 'Ошибка загрузки истории');
    }
}

function renderDeliveredList(container, orders) {
    if (!orders || orders.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                    </svg>
                </div>
                <div class="empty-state-title">История пуста</div>
                <div class="empty-state-text">Выданные заказы появятся здесь</div>
            </div>
        `;
        return;
    }
    
    // Группируем по order_id
    const grouped = groupByOrderId(orders);
    
    const historyHtml = Object.entries(grouped).map(([orderId, items]) => {
        const orderTotal = items.reduce((sum, item) => sum + (item.price_with_sale || item.price || 0), 0);
        const buyerName = items[0].buyer_name || items[0].display_name || 'Клиент';
        const buyerSid = items[0].buyer_sid || items[0].user_sid;
        const itemsHtml = items.map(item => {
            const vendorCode = item.vendor_code ? String(item.vendor_code) : '';
            const fallbackUrl = item.image_url || '';
            const imgSrc = getInitialImageSrc(vendorCode, fallbackUrl);
            return `
                <div class="order-item-mini" onclick="openDeliveredGoodsModal(${JSON.stringify(item).replace(/"/g, '&quot;')})">
                    <img src="${imgSrc}" alt="" data-vendor="${vendorCode}" data-fallback="${fallbackUrl}" loading="lazy"
                         onerror="if(window.retryImage) window.retryImage(this); else this.src='/static/img/no-image.svg';">
                    <div class="order-item-info">
                        <div class="order-item-name">${item.info?.name || 'Товар'}</div>
                        <div class="order-item-barcode">${item.scanned_code || '-'}</div>
                    </div>
                    <div class="order-item-price">${formatPrice(item.price_with_sale || item.price)}</div>
                </div>
            `;
        }).join('');
        const deliveredAt = formatDate(items[0].delivery_timestamp, { verbose: true, withSeconds: true });
        return `
            <div class="order-group">
                <div class="order-group-header">
                    <div class="order-id">Заказ #${orderId.substring(0, 8)}...</div>
                    ${buyerSid ? `<a href="/buyer/${buyerSid}" class="order-buyer" onclick="event.stopPropagation()">👤 ${buyerName}</a>` : ''}
                    <div class="order-count">${items.length} товар${getPlural(items.length)}</div>
                    <div class="order-total">${formatPrice(orderTotal)}</div>
                    <div class="order-date">${deliveredAt ? `Выдан ${deliveredAt}` : ''}</div>
                </div>
                <div class="order-items">
                    ${itemsHtml}
                </div>
            </div>
        `;
    }).join('');
    container.innerHTML = historyHtml;
    hydrateVendorImages(container, '.order-item-mini img[data-vendor]', false, { defer: true });
}

function groupByOrderId(orders) {
    // Группируем по order_id, если он есть
    // Если order_id нет (null), группируем по buyer_sid + время выдачи (с точностью до минуты)
    return orders.reduce((acc, order) => {
        let id;
        
        if (order.order_id) {
            // Есть order_id - используем его
            id = String(order.order_id);
        } else {
            // Нет order_id - группируем по клиенту + время
            const buyerSid = order.buyer_sid || 'unknown';
            // Округляем время до минуты (60000 мс)
            const timeKey = order.delivery_timestamp ? Math.floor(order.delivery_timestamp / 60000) : 0;
            id = `${buyerSid}_${timeKey}`;
        }
        
        id = id || 'unknown';
        if (!acc[id]) acc[id] = [];
        acc[id].push(order);
        return acc;
    }, {});
}

function getPlural(n) {
    if (n === 1) return '';
    if (n >= 2 && n <= 4) return 'а';
    return 'ов';
}

// ========== STATS ==========

async function loadStats() {
    try {
        const stats = await API.get('/stats');
        
        document.querySelectorAll('[data-stat]').forEach(el => {
            const key = el.dataset.stat;
            if (stats[key] !== undefined) {
                animateNumber(el, stats[key]);
            }
        });
    } catch (err) {
        console.error('Load stats error:', err);
    }
}

function animateNumber(element, target) {
    const duration = 600;
    const start = parseInt(element.textContent) || 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * eased);
        
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// ========== HELPERS ==========

function showLoading(container) {
    container.innerHTML = `
        <div class="loading">
            <div class="loading-spinner"></div>
            <span>Загрузка...</span>
        </div>
    `;
}

function showError(container, message) {
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon" style="background: var(--status-declined-bg);">
                <svg width="40" height="40" fill="none" stroke="var(--status-declined)" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                </svg>
            </div>
            <div class="empty-state-title">${message}</div>
            <button class="btn btn-secondary" onclick="location.reload()">Обновить страницу</button>
        </div>
    `;
}

// ========== BUYER PROFILE ==========

async function updateBuyerCustomData(userSid, data) {
    try {
        await API.post(`/buyer/${userSid}/custom`, data);
        Toast.success('Данные обновлены');
        return true;
    } catch (err) {
        Toast.error('Ошибка сохранения');
        return false;
    }
}

function initBuyerProfile() {
    const editNameBtn = document.getElementById('edit-name-btn');
    const saveNameBtn = document.getElementById('save-name-btn');
    const nameInput = document.getElementById('buyer-custom-name');
    const descInput = document.getElementById('buyer-description');
    
    if (editNameBtn && nameInput) {
        editNameBtn.onclick = () => {
            nameInput.disabled = false;
            nameInput.focus();
            editNameBtn.style.display = 'none';
            saveNameBtn.style.display = 'inline-flex';
        };
        
        saveNameBtn.onclick = async () => {
            const userSid = document.getElementById('buyer-profile').dataset.userSid;
            const success = await updateBuyerCustomData(userSid, {
                custom_name: nameInput.value
            });
            
            if (success) {
                nameInput.disabled = true;
                editNameBtn.style.display = 'inline-flex';
                saveNameBtn.style.display = 'none';
            }
        };
    }
    
    if (descInput) {
        let saveTimeout;
        descInput.oninput = () => {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(async () => {
                const userSid = document.getElementById('buyer-profile').dataset.userSid;
                await updateBuyerCustomData(userSid, {
                    description: descInput.value
                });
            }, 1000);
        };
    }
}

// ========== TABS ==========

function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.onclick = () => {
            const target = tab.dataset.tab;
            
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            contents.forEach(c => {
                c.style.display = c.id === `tab-${target}` ? 'block' : 'none';
            });
            scheduleTabHydration(target);
        };
    });

    const initial = document.querySelector('.tab.active');
    if (initial && initial.dataset.tab) {
        scheduleTabHydration(initial.dataset.tab);
    }
}

function scheduleTabHydration(tabId) {
    if (!isAutoImageLoadingEnabled()) return;
    const container = document.getElementById(`tab-${tabId}`);
    if (!container || !container.querySelector('img[data-vendor]')) return;
    requestAnimationFrame(() => {
        hydrateVendorImages(container, 'img[data-vendor]', true, { defer: true });
    });
}

// ========== CRITICAL SETTINGS ==========

function openCriticalSettings() {
    const modal = document.getElementById('critical-settings-modal');
    if (!modal) return;
    
    // Обновляем счётчик кэша
    updateImageCacheCount();
    syncAutoImageToggleUI();
    
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeCriticalSettings() {
    const modal = document.getElementById('critical-settings-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function updateImageCacheCount() {
    const countEl = document.getElementById('image-cache-count');
    if (!countEl) return;
    
    try {
        const cached = JSON.parse(localStorage.getItem('workingImageUrls') || '{}');
        const count = Object.keys(cached).length;
        countEl.textContent = `Сохранено URL: ${count}`;
    } catch {
        countEl.textContent = 'Не удалось прочитать кэш';
    }
}

function clearImageCache() {
    const count = Object.keys(workingImageUrls || {}).length;
    
    if (!confirm(`⚠️ Вы уверены?\n\nБудет удалено ${count} сохранённых URL картинок.\nПосле очистки картинки будут загружаться заново при открытии страниц с товарами.`)) {
        return;
    }
    
    try {
        // Очищаем localStorage
        localStorage.removeItem('workingImageUrls');
        
        // Очищаем объект в памяти
        if (typeof workingImageUrls !== 'undefined') {
            Object.keys(workingImageUrls).forEach(k => delete workingImageUrls[k]);
        }
        
        // Очищаем Set неудачных попыток
        if (typeof failedImageUrls !== 'undefined') {
            failedImageUrls.clear();
        }
        
        Toast.success(`Кэш очищен (${count} URL)`);
        updateImageCacheCount();
        
        // Перезагружаем страницу через секунду
        setTimeout(() => location.reload(), 1000);
    } catch (e) {
        Toast.error('Ошибка очистки кэша');
        console.error(e);
    }
}

// Принудительное обновление картинки товара
function refreshGoodsImage(event, vendorCode) {
    event.stopPropagation();
    
    if (!vendorCode) return;
    const code = String(vendorCode);
    
    // Удаляем из кэша
    if (typeof workingImageUrls !== 'undefined') {
        delete workingImageUrls[code];
    }
    if (typeof failedImageUrls !== 'undefined') {
        failedImageUrls.delete(code);
    }
    markVendorImagesPending(code);
    
    // Находим картинку
    const img = event.target.closest('.goods-image-wrapper')?.querySelector('img') ||
                event.target.closest('.goods-card')?.querySelector('img[data-vendor]');
    if (img) {
        registerVendorImage(img, code);
    }

    if (img) {
        loadImageImmediately(img, code);
        Toast.info('Загружаю картинку...');
    }
}

// Обновление картинки в модальном окне
let currentModalVendorCode = null;

function refreshModalImage() {
    if (!currentModalVendorCode) return;
    
    const vendorCode = currentModalVendorCode;
    
    // Удаляем из кэша
    if (typeof workingImageUrls !== 'undefined') {
        delete workingImageUrls[vendorCode];
    }
    if (typeof failedImageUrls !== 'undefined') {
        failedImageUrls.delete(vendorCode);
    }
    markVendorImagesPending(vendorCode);
    
    const modal = document.getElementById('goods-modal');
    const img = modal?.querySelector('.goods-modal-image');
    if (img) {
        registerVendorImage(img, vendorCode);
    }
    
    if (img) {
        loadImageImmediately(img, vendorCode);
        Toast.info('Загружаю картинку...');
    }
}

// Немедленная загрузка картинки (принудительное обновление)
async function loadImageImmediately(img, vendorCode) {
    const code = vendorCode ? String(vendorCode) : '';
    if (!code) return;
    if (img) {
        registerVendorImage(img, code);
    }

    Toast.info('Загрузка картинки...');

    try {
        // Вызываем endpoint для скачивания в кэш
        const response = await API.post(`/image/cache/${code}`);

        if (response.success && response.url) {
            workingImageUrls[code] = response.url;
            saveImageCache();
            // Удаляем из failed, если было там
            failedImageUrls.delete(code);
            setVendorImagesSource(code, response.url);
            Toast.success('Картинка загружена');
        } else {
            Toast.error('Картинка не найдена на WB');
            failedImageUrls.add(code);
        }
    } catch (e) {
        console.error(e);
        Toast.error('Ошибка загрузки');
        failedImageUrls.add(code);
    }
}

async function checkVisibleImagesStatus() {
    const images = document.querySelectorAll('img[data-vendor][src*="no-image"]');
    if (!images.length) return;

    const codes = new Set();
    images.forEach(img => {
        if (isElementVisible(img)) {
            codes.add(img.dataset.vendor);
        }
    });

    if (codes.size === 0) return;

    try {
        const result = await API.post('/images/check-status', { codes: Array.from(codes) });

        let updatedCount = 0;
        Object.entries(result).forEach(([code, url]) => {
            if (url) {
                workingImageUrls[code] = url;
                failedImageUrls.delete(code);
                updatedCount += setVendorImagesSource(code, url);
            }
        });

        if (updatedCount > 0) {
            saveImageCache();
        }
    } catch (e) {
        console.error('Error checking images status', e);
    }
}

async function updateAllBuyerImages(userSid, type = 'all') {
    const promptText = type === 'all'
        ? 'Загрузить картинки для всех товаров клиента?'
        : (type === 'ready' ? 'Загрузить картинки для товаров "Готово к выдаче"?' : 'Загрузить картинки для товаров "В пути"?');

    if (!confirm(promptText + ' Это может занять некоторое время.')) return;

    let progressToast = null;
    try {
        progressToast = Toast.persistent('Запуск загрузки...', 'info');

        const res = await API.post(`/buyer/${userSid}/cache-images`, { type });
        if (res.success) {
            // Очищаем список неудачных попыток сразу
            if (typeof failedImageUrls !== 'undefined') {
                document.querySelectorAll('img[data-vendor]').forEach(img => {
                    const code = img.dataset.vendor;
                    if (code) failedImageUrls.delete(code);
                });
            }

            // Запускаем поллинг прогресса
            let isFinished = false;
            const pollInterval = setInterval(async () => {
                try {
                    const status = await API.get(`/buyer/${userSid}/download-progress`);

                    if (status.finished) {
                        isFinished = true;
                        clearInterval(pollInterval);
                        if (progressToast) progressToast.remove();
                        Toast.success(`Загрузка завершена (${status.total} товаров)`);
                        // Финальное обновление
                        if (typeof failedImageUrls !== 'undefined') {
                            document.querySelectorAll('img[data-vendor]').forEach(img => {
                                const code = img.dataset.vendor;
                                if (code) failedImageUrls.delete(code);
                            });
                        }
                        await checkVisibleImagesStatus();
                        loadVisiblePendingImages();
                        return;
                    }

                    if (progressToast) {
                        progressToast.update(`Скачано ${status.current} из ${status.total}`);
                    }

                    // Сбрасываем кэш ошибок для видимых картинок, чтобы они перепроверились
                    if (typeof failedImageUrls !== 'undefined') {
                        document.querySelectorAll('img[data-vendor]').forEach(img => {
                            const code = img.dataset.vendor;
                            if (code) failedImageUrls.delete(code);
                        });
                    }

                    // Проверяем статус картинок на сервере
                    await checkVisibleImagesStatus();

                    // Обновляем картинки на экране
                    loadVisiblePendingImages();

                } catch (e) {
                    console.error('Progress poll error', e);
                }
            }, 1000);

            // Предохранитель на 5 минут
            setTimeout(() => {
                if (!isFinished) {
                    clearInterval(pollInterval);
                    if (progressToast) progressToast.remove();
                    Toast.info('Загрузка продолжается в фоне...');
                }
            }, 300000);

        } else {
            if (progressToast) progressToast.remove();
            Toast.info(res.message || 'Процесс уже идет');
        }
    } catch (e) {
        if (progressToast) progressToast.remove();
        Toast.error('Ошибка запуска загрузки');
    }
}

// Глобальные функции
window.openCriticalSettings = openCriticalSettings;
window.closeCriticalSettings = closeCriticalSettings;
window.clearImageCache = clearImageCache;
window.refreshGoodsImage = refreshGoodsImage;
window.refreshModalImage = refreshModalImage;
window.openProfileGoodsCard = openProfileGoodsCard;
window.updateAllBuyerImages = updateAllBuyerImages;

// ========== INIT ==========

document.addEventListener('DOMContentLoaded', () => {
    Toast.init();
    initAutoImageLoadingControls();
    initNavigation();
    initSearch();
    initInlineSearches();
    initTabs();
    
    // Загрузка статистики на главной
    if (document.querySelector('[data-stat]')) {
        scheduleHydrationTask(() => loadStats(), { timeout: 200 });
    }
    
    // Загрузка товаров
    const goodsContainer = document.getElementById('goods-container');
    if (goodsContainer) {
        showLoading(goodsContainer);
        const type = goodsContainer.dataset.type || 'pickup';
        scheduleHydrationTask(() => loadGoods(goodsContainer, type), { timeout: 220 });
    }
    
    // Загрузка клиентов
    const buyersContainer = document.getElementById('buyers-container');
    if (buyersContainer) {
        showLoading(buyersContainer);
        scheduleHydrationTask(() => loadBuyers(buyersContainer), { timeout: 260 });
    }
    
    // Загрузка излишков
    const surplusContainer = document.getElementById('surplus-container');
    if (surplusContainer) {
        showLoading(surplusContainer);
        scheduleHydrationTask(() => loadSurplus(surplusContainer), { timeout: 320 });
    }
    
    // Загрузка истории
    const historyContainer = document.getElementById('history-container');
    if (historyContainer) {
        showLoading(historyContainer);
        scheduleHydrationTask(() => loadDelivered(historyContainer), { timeout: 380 });
    }
    
    // Профиль покупателя
    if (document.getElementById('buyer-profile')) {
        scheduleHydrationTask(() => initBuyerProfile(), { timeout: 180 });
    }
    
    // Закрытие модалей
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAllModals();
    });
});

// ========== DELIVERED GOODS MODAL ==========

let currentDeliveredGoodsUid = null;

function openDeliveredGoodsModal(item) {
    // Сохраняем goods_uid для кнопки "Весь заказ"
    currentDeliveredGoodsUid = item.goods_uid;
    
    // Преобразуем данные выданного товара в формат для openGoodsModal
    const goods = {
        scanned_code: item.scanned_code,
        vendor_code: item.vendor_code,
        info: item.info || {},
        price: item.price,
        price_with_sale: item.price_with_sale,
        buyer_sid: item.buyer_sid,
        buyer_mobile: item.buyer_mobile,
        status: 'GOODS_RECIEVED', // Выдан
        image_url: item.image_url,
        goods_uid: item.goods_uid,
        status_updated: item.status_updated || item.delivery_timestamp || item.timestamp,
        delivery_timestamp: item.delivery_timestamp || item.timestamp
    };
    
    // Открываем стандартную модалку
    openGoodsModal(goods);
    
    // Показываем кнопку "Весь заказ"
    const orderBtn = document.querySelector('[data-field="order-link"]');
    if (orderBtn) {
        orderBtn.style.display = 'inline-flex';
    }
}

async function showFullOrder() {
    if (!currentDeliveredGoodsUid) return;
    
    closeModal('goods-modal');
    
    try {
        const data = await API.get(`/delivered/order/${currentDeliveredGoodsUid}`);
        
        if (data.orders && data.orders.length > 0) {
            // Показываем модалку с заказом
            showOrderModal(data.orders);
        }
    } catch (err) {
        console.error('Error loading order:', err);
        Toast.error('Ошибка загрузки заказа');
    }
}

async function openOrderByGoodsUid(goodsUid) {
    if (!goodsUid) {
        Toast.info('Не удалось определить заказ');
        return;
    }
    try {
        const data = await API.get(`/delivered/order/${goodsUid}`);
        if (data.orders && data.orders.length > 0) {
            showOrderModal(data.orders);
        } else {
            Toast.info('Заказ не найден');
        }
    } catch (err) {
        console.error('Error opening order modal:', err);
        Toast.error('Ошибка загрузки заказа');
    }
}

function showOrderModal(orders) {
    let modal = document.getElementById('order-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'order-modal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }
    
    const orderTotal = orders.reduce((sum, item) => sum + (item.price_with_sale || item.price || 0), 0);
    const buyerName = orders[0].buyer_name || 'Клиент';
    const buyerSid = orders[0].buyer_sid;
    const deliveredAt = formatDate(orders[0].delivery_timestamp, { verbose: true, withSeconds: true });
    
    const modalItems = orders.map(item => {
        const vendorCode = item.vendor_code ? String(item.vendor_code) : '';
        const fallbackUrl = item.image_url || '';
        const imgSrc = getInitialImageSrc(vendorCode, fallbackUrl);
        return `
            <div class="order-modal-item" onclick="openDeliveredGoodsModal(${JSON.stringify(item).replace(/"/g, '&quot;')})">
                <img src="${imgSrc}" alt="" data-vendor="${vendorCode}" data-fallback="${fallbackUrl}" loading="lazy"
                     onerror="if(window.retryImage) window.retryImage(this); else this.src='/static/img/no-image.svg';">
                <div class="order-modal-item-info">
                    <div class="order-modal-item-brand">${item.info?.brand || ''}</div>
                    <div class="order-modal-item-name">${item.info?.name || 'Товар'}</div>
                    <div class="order-modal-item-barcode" onclick="event.stopPropagation(); copyToClipboard('${item.scanned_code}')">${item.scanned_code || '-'}</div>
                </div>
                <div class="order-modal-item-price">${formatPrice(item.price_with_sale || item.price)}</div>
            </div>
        `;
    }).join('');
    modal.innerHTML = `
        <div class="modal modal-order">
            <div class="modal-header">
                <h3 class="modal-title">Заказ (${orders.length} товар${getPlural(orders.length)})</h3>
                <button class="modal-close" onclick="closeModal('order-modal')">
                    <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="order-modal-header">
                    ${buyerSid ? `<a href="/buyer/${buyerSid}" class="order-buyer-link">👤 ${buyerName}</a>` : `<span>👤 ${buyerName}</span>`}
                    <div class="order-modal-total">${formatPrice(orderTotal)}</div>
                    <div class="order-modal-date">${deliveredAt ? `Выдан ${deliveredAt}` : ''}</div>
                </div>
                <div class="order-modal-items">
                    ${modalItems}
                </div>
            </div>
        </div>
    `;
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal('order-modal');
    });
    
    openModal('order-modal');
    hydrateVendorImages(modal, '.order-modal-item img[data-vendor]', true, { defer: true });
}


async function updateBuyerCategoryImages(userSid, type) {
    const typeLabels = {
        'ready': 'Готово к выдаче',
        'onway': 'В пути'
    };
    const label = typeLabels[type] || type;

    if (!confirm(`Загрузить картинки для категории "${label}"?`)) return;

    let progressToast = null;
    try {
        progressToast = Toast.persistent(`Загрузка категории "${label}"...`, 'info');

        const res = await API.post(`/buyer/${userSid}/cache-images`, { type });
        if (res.success) {
            // Очищаем список неудачных попыток сразу
            if (typeof failedImageUrls !== 'undefined') {
                document.querySelectorAll('img[data-vendor]').forEach(img => {
                    const code = img.dataset.vendor;
                    if (code) failedImageUrls.delete(code);
                });
            }

            // Запускаем поллинг прогресса
            let isFinished = false;
            const pollInterval = setInterval(async () => {
                try {
                    const status = await API.get(`/buyer/${userSid}/download-progress`);

                    if (status.finished) {
                        isFinished = true;
                        clearInterval(pollInterval);
                        if (progressToast) progressToast.remove();
                        Toast.success(`Загрузка завершена (${status.total} товаров)`);

                        // Финальное обновление
                        if (typeof failedImageUrls !== 'undefined') {
                            document.querySelectorAll('img[data-vendor]').forEach(img => {
                                const code = img.dataset.vendor;
                                if (code) failedImageUrls.delete(code);
                            });
                        }

                        // Если есть функции обновления UI
                        if (typeof checkVisibleImagesStatus === 'function') {
                            await checkVisibleImagesStatus();
                        }
                        if (typeof loadVisiblePendingImages === 'function') {
                            loadVisiblePendingImages();
                        }

                        // Обновляем список товаров в секции если она открыта
                        const section = document.querySelector(`.tryon-goods-section[data-buyer="${userSid}"][data-type="${type}"]`);
                        if (section && section.classList.contains('expanded')) {
                            // Перезагружаем список чтобы отобразить картинки
                            const list = section.querySelector('.tryon-goods-list');
                            if (list) {
                                // Сбрасываем кэш списка чтобы он перерисовался
                                if (typeof tryOnGoodsCache !== 'undefined') {
                                    const cacheKey = `${userSid}:${type}`;
                                    tryOnGoodsCache.delete(cacheKey);
                                }
                                section.dataset.loaded = 'false';
                                toggleTryOnGoodsSection(section, { user_sid: userSid }, type);
                            }
                        }
                        return;
                    }

                    if (progressToast) {
                        progressToast.update(`Скачано ${status.current} из ${status.total}`);
                    }

                } catch (e) {
                    console.error('Progress poll error', e);
                }
            }, 1000);

            // Предохранитель на 5 минут
            setTimeout(() => {
                if (!isFinished) {
                    clearInterval(pollInterval);
                    if (progressToast) progressToast.remove();
                    Toast.info('Загрузка продолжается в фоне...');
                }
            }, 300000);

        } else {
            if (progressToast) progressToast.remove();
            Toast.info(res.message || 'Процесс уже идет');
        }
    } catch (e) {
        console.error(e);
        if (progressToast) progressToast.remove();
        Toast.error('Ошибка запуска загрузки');
    }
}

// Экспорт новой функции
window.updateBuyerCategoryImages = updateBuyerCategoryImages;
