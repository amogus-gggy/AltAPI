# Rate Limiting в AltAPI

**Rate Limiting** (ограничение частоты запросов) — механизм контроля количества запросов, которые клиент может отправить за определённый период времени. Это важная часть защиты API от злоупотреблений, DDoS-атак и чрезмерной нагрузки на сервер.

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Декоратор @rate_limit](#декоратор-rate_limit)
- [Декоратор @rate_limit_batch](#декоратор-rate_limit_batch)
- [Как это работает](#как-это-работает)
- [Кастомизация](#кастомизация)
  - [Свои функции для ключей](#свои-функции-для-ключей)
  - [Свои условия пропуска](#свои-условия-пропуска)
- [HTTP заголовки](#http-заголовки)
- [Полный пример](#полный-пример)

---

## Быстрый старт

Rate limiting в AltAPI максимально прост в использовании. Всё, что нужно — импортировать декоратор:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.ratelimit import rate_limit

app = AltAPI()


@app.get("/api/data")
@rate_limit(limit=10, period=60)  # 10 запросов в минуту
async def get_data(request):
    return JSONResponse({"data": "value"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

### Ключевые особенности

- ✅ **Простой импорт** — просто `from altapi.ratelimit import rate_limit`
- ✅ **Никакой настройки** — менеджер запускается автоматически при `app.run()`
- ✅ **Multi-worker поддержка** — все данные хранятся в центральном процессе
- ✅ **Готово к продакшену** — работает из коробки

### Что происходит при превышении лимита

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Try again in 45 seconds."
}
```

---

## Декоратор @rate_limit

Основной декоратор для ограничения частоты запросов.

### Синтаксис

```python
from altapi.ratelimit import rate_limit


@app.get("/api/endpoint")
@rate_limit(
    limit=10,           # Максимум запросов
    period=60,          # Период в секундах
    key_func=None,      # Функция для получения ключа
    skip_when=None      # Условие пропуска
)
async def my_endpoint(request):
    ...
```

### Параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `limit` | `int` | `10` | Максимальное количество запросов за период |
| `period` | `float` | `60` | Длительность периода в секундах |
| `key_func` | `Callable` | `None` | Функция для извлечения уникального ключа из запроса |
| `skip_when` | `Callable` | `None` | Функция, определяющая, когда пропускать ограничение |

---

### Параметры limit и period

**`limit`** — максимальное количество запросов, разрешённых за один период.

**`period`** — длительность периода в секундах.

#### Примеры

```python
# 5 запросов в секунду
@rate_limit(limit=5, period=1)
async def fast_endpoint(request):
    ...

# 100 запросов в минуту
@rate_limit(limit=100, period=60)
async def normal_endpoint(request):
    ...

# 1000 запросов в час
@rate_limit(limit=1000, period=3600)
async def hourly_endpoint(request):
    ...

# 10000 запросов в день
@rate_limit(limit=10000, period=86400)
async def daily_endpoint(request):
    ...
```

---

### Параметр key_func

**`key_func`** — функция, которая извлекает уникальный идентификатор из запроса. По умолчанию используется IP-адрес клиента.

#### Функция по умолчанию (IP-адрес)

```python
# Внутренняя реализация по умолчанию
def default_key_func(request):
    return request.client.host if request.client else "unknown"
```

#### Кастомная функция для ключа

```python
def get_api_key(request):
    """Получение ключа из заголовка X-API-Key."""
    return request.headers.get("X-API-Key", "anonymous")


@app.get("/api/premium")
@rate_limit(limit=100, period=60, key_func=get_api_key)
async def premium_endpoint(request):
    return JSONResponse({"premium": "data"})
```

#### Асинхронная функция для ключа

```python
async def get_user_key(request):
    """Асинхронное получение ключа пользователя."""
    token = request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        # Здесь может быть проверка токена в БД
        user_id = await get_user_id_from_token(token[7:])
        return f"user:{user_id}"
    return "anonymous"


@app.get("/api/user")
@rate_limit(limit=50, period=60, key_func=get_user_key)
async def user_endpoint(request):
    return JSONResponse({"user": "data"})
```

---

### Параметр skip_when

**`skip_when`** — функция, определяющая, когда следует пропустить проверку rate limiting. Возвращает `True` для пропуска или `False` для применения ограничения.

#### Пропуск для администраторов

```python
def is_admin(request):
    """Пропустить rate limiting для администраторов."""
    admin_key = request.headers.get("X-Admin-Key", "")
    return admin_key == "supersecretadminkey"


@app.get("/api/admin")
@rate_limit(limit=10, period=60, skip_when=is_admin)
async def admin_endpoint(request):
    return JSONResponse({"admin": "data"})
```

#### Пропуск для локальных запросов

```python
def is_local(request):
    """Пропустить rate limiting для локальных запросов."""
    return request.client.host in ("127.0.0.1", "localhost")


@app.get("/api/internal")
@rate_limit(limit=100, period=60, skip_when=is_local)
async def internal_endpoint(request):
    return JSONResponse({"internal": "data"})
```

#### Асинхронная проверка

```python
async def has_premium_access(request):
    """Пропустить rate limiting для премиум-пользователей."""
    api_key = request.headers.get("X-API-Key", "")
    # Проверка в БД или кэше
    is_premium = await check_premium_status(api_key)
    return is_premium


@app.get("/api/premium")
@rate_limit(limit=100, period=60, skip_when=has_premium_access)
async def premium_endpoint(request):
    return JSONResponse({"premium": "data"})
```

---

## Декоратор @rate_limit_batch

Декоратор для применения **нескольких лимитов одновременно** к одному эндпоинту.

### Синтаксис

```python
from altapi.ratelimit import rate_limit_batch


@app.get("/api/endpoint")
@rate_limit_batch(
    limits=[
        (10, 60),      # 10 запросов в минуту
        (100, 3600),   # 100 запросов в час
        (1000, 86400)  # 1000 запросов в день
    ],
    key_func=None     # Функция для получения ключа
)
async def my_endpoint(request):
    ...
```

### Параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `limits` | `List[Tuple[int, float]]` | **Обязательный** | Список кортежей `(limit, period)` |
| `key_func` | `Callable` | `None` | Функция для извлечения ключа |

### Как работает

Все лимиты проверяются **одновременно**. Если **любой** лимит превышен, возвращается ошибка 429.

```
Запрос → Проверка лимита 1 (10/мин) → OK
       → Проверка лимита 2 (100/час) → OK
       → Проверка лимита 3 (1000/день) → OK
       → Разрешить запрос
```

### Примеры

#### Стандартный API

```python
@app.get("/api/data")
@rate_limit_batch([
    (10, 60),      # 10 запросов в минуту
    (100, 3600),   # 100 запросов в час
    (1000, 86400)  # 1000 запросов в день
])
async def get_data(request):
    return JSONResponse({"data": "value"})
```

#### Строгий лимит для аутентификации

```python
@app.post("/api/login")
@rate_limit_batch([
    (5, 60),       # 5 попыток в минуту
    (20, 3600),    # 20 попыток в час
    (50, 86400)    # 50 попыток в день
])
async def login(request):
    data = await request.json()
    # Логика аутентификации
    return JSONResponse({"token": "..."})
```

#### Публичный API с разными уровнями

```python
@app.get("/api/public")
@rate_limit_batch([
    (30, 60),      # 30 запросов в минуту
    (500, 3600)    # 500 запросов в час
])
async def public_api(request):
    return JSONResponse({"public": "data"})
```

---

## Как это работает

### Архитектура

AltAPI использует **централизованный менеджер** для хранения данных rate limiting. Это обеспечивает работу в multi-worker режиме без дополнительной настройки.

```
┌─────────────────────────────────────────────────────────┐
│                  Shared Manager Process                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Rate Limit Store                   │    │
│  │              (in-memory)                        │    │
│  └─────────────────────────────────────────────────┘    │
│                    TCP: 127.0.0.1:58000                 │
└─────────────────────────────────────────────────────────┘
           ▲                    ▲                    ▲
           │                    │                    │
    ┌──────┴──────┐      ┌──────┴──────┐      ┌──────┴──────┐
    │  Worker 1   │      │  Worker 2   │      │  Worker 3   │
    │  (uvicorn)  │      │  (uvicorn)  │      │  (uvicorn)  │
    └─────────────┘      └─────────────┘      └─────────────┘
```

### Автоматический запуск

Менеджер запускается **автоматически** при вызове `app.run()`:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    # Менеджер запущен автоматически!
```

При остановке приложения менеджер также останавливается корректно.

### Преимущества

- **Никакой настройки** — работает из коробки
- **Multi-worker поддержка** — все воркеры видят общее состояние
- **Автоматическое переподключение** — при разрыве соединения
- **Централизованное хранение** — данные в одном процессе

---

## Кастомизация

### Свои функции для ключей

Функция ключа определяет, как идентифицировать клиента. По умолчанию используется IP-адрес.

#### По API-ключу

```python
def get_api_key(request):
    """Идентификация по заголовку X-API-Key."""
    return request.headers.get("X-API-Key", "anonymous")


@app.get("/api/data")
@rate_limit(limit=100, period=60, key_func=get_api_key)
async def get_data(request):
    return JSONResponse({"data": "value"})
```

#### По пользователю (из токена)

```python
async def get_user_id(request):
    """Идентификация по JWT токену."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return "anonymous"

    token = auth_header[7:]
    # Здесь декодирование JWT и получение user_id
    try:
        payload = decode_jwt(token)
        return f"user:{payload['sub']}"
    except Exception:
        return "anonymous"


@app.get("/api/user/profile")
@rate_limit(limit=50, period=60, key_func=get_user_id)
async def get_profile(request):
    return JSONResponse({"profile": "data"})
```

#### По комбинации параметров

```python
def get_combined_key(request):
    """Ключ на основе IP и User-Agent."""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    return f"{ip}:{user_agent}"


@app.get("/api/browser")
@rate_limit(limit=100, period=60, key_func=get_combined_key)
async def browser_endpoint(request):
    return JSONResponse({"browser": "data"})
```

---

### Свои условия пропуска

Функция `skip_when` определяет, когда не применять rate limiting.

#### Пропуск для внутренних IP

```python
def is_internal(request):
    """Пропустить для внутренних IP."""
    internal_ips = ["10.", "172.16.", "172.17.", "192.168."]
    ip = request.client.host if request.client else ""
    return any(ip.startswith(prefix) for prefix in internal_ips)


@app.get("/api/internal")
@rate_limit(limit=10, period=60, skip_when=is_internal)
async def internal_endpoint(request):
    return JSONResponse({"internal": "data"})
```

#### Пропуск в режиме отладки

```python
import os

def is_debug_mode(request):
    """Пропустить в режиме отладки."""
    return os.getenv("DEBUG", "false").lower() == "true"


@app.get("/api/debug")
@rate_limit(limit=5, period=60, skip_when=is_debug_mode)
async def debug_endpoint(request):
    return JSONResponse({"debug": "data"})
```

#### Пропуск для whitelist ключей

```python
WHITELIST_KEYS = {"premium-key-1", "premium-key-2", "admin-key"}

def is_whitelisted(request):
    """Пропустить для ключей из whitelist."""
    api_key = request.headers.get("X-API-Key", "")
    return api_key in WHITELIST_KEYS


@app.get("/api/premium")
@rate_limit(limit=100, period=60, skip_when=is_whitelisted)
async def premium_endpoint(request):
    return JSONResponse({"premium": "data"})
```

---

## HTTP заголовки

AltAPI добавляет стандартные заголовки rate limiting к ответам.

### Заголовки в успешном ответе

```
X-RateLimit-Limit: 10          # Максимум запросов за период
X-RateLimit-Remaining: 7       # Осталось запросов
X-RateLimit-Reset: 1711737600  # Время сброса (Unix timestamp)
```

### Заголовки при превышении лимита (429)

```
X-RateLimit-Limit: 10          # Максимум запросов за период
X-RateLimit-Remaining: 0       # Осталось запросов
X-RateLimit-Reset: 1711737600  # Время сброса (Unix timestamp)
Retry-After: 45                # Секунд до сброса
```

### Пример ответа при 429

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1711737600
Retry-After: 45

{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Try again in 45 seconds."
}
```

### Чтение заголовков на клиенте

```python
import requests

response = requests.get("http://localhost:8000/api/data")

# Проверка лимитов
limit = response.headers.get("X-RateLimit-Limit")
remaining = response.headers.get("X-RateLimit-Remaining")
reset = response.headers.get("X-RateLimit-Reset")

print(f"Лимит: {limit}, Осталось: {remaining}, Сброс: {reset}")

# Обработка 429
if response.status_code == 429:
    retry_after = response.headers.get("Retry-After")
    print(f"Повторить через {retry_after} секунд")
```

---

## Полный пример

```python
"""
Полный пример использования rate limiting в AltAPI.
"""

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.ratelimit import rate_limit, rate_limit_batch

# Инициализация приложения
app = AltAPI()


# === Функции для ключей ===

def get_api_key(request):
    """Получение ключа из заголовка."""
    return request.headers.get("X-API-Key", "anonymous")


async def get_user_id(request):
    """Получение ID пользователя из токена."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        # Здесь может быть декодирование JWT
        return f"user:authenticated"
    return "anonymous"


def is_admin(request):
    """Проверка на администратора."""
    return request.headers.get("X-Admin-Key") == "admin-secret"


def is_local(request):
    """Проверка на локальный запрос."""
    return request.client.host in ("127.0.0.1", "localhost")


# === Эндпоинты ===

@app.get("/")
async def home(request):
    """Главная страница без ограничений."""
    return JSONResponse({"message": "Welcome to AltAPI!"})


@app.get("/api/public")
@rate_limit(limit=30, period=60)  # 30 запросов в минуту
async def public_api(request):
    """Публичный API с базовым лимитом."""
    return JSONResponse({"data": "public"})


@app.get("/api/registered")
@rate_limit(limit=100, period=60, key_func=get_api_key)  # 100 запросов в минуту по API ключу
async def registered_api(request):
    """API для зарегистрированных пользователей."""
    return JSONResponse({"data": "registered"})


@app.get("/api/premium")
@rate_limit_batch([
    (10, 60),      # 10 запросов в минуту
    (100, 3600),   # 100 запросов в час
    (1000, 86400)  # 1000 запросов в день
])
async def premium_api(request):
    """Premium API с несколькими лимитами."""
    return JSONResponse({"data": "premium"})


@app.get("/api/critical")
@rate_limit(
    limit=5,
    period=60,
    skip_when=is_admin  # Пропуск для администраторов
)
async def critical_api(request):
    """Критичный API с особыми настройками."""
    return JSONResponse({"data": "critical"})


@app.post("/api/login")
@rate_limit_batch([
    (5, 60),       # 5 попыток в минуту
    (20, 3600),    # 20 попыток в час
    (50, 86400)    # 50 попыток в день
])
async def login(request):
    """Аутентификация со строгими лимитами."""
    data = await request.json()
    # Логика аутентификации...
    return JSONResponse({"token": "example-token"})


@app.get("/api/internal")
@rate_limit(limit=1000, period=60, skip_when=is_local)  # Пропуск для локальных
async def internal_api(request):
    """Внутренний API с пропуском для локальных запросов."""
    return JSONResponse({"data": "internal"})


# === Запуск ===

if __name__ == "__main__":
    print("Endpoints:")
    print("  GET  /             - No limit")
    print("  GET  /api/public   - 30 req/min")
    print("  GET  /api/registered - 100 req/min (by API key)")
    print("  GET  /api/premium  - 10/min, 100/hour, 1000/day")
    print("  GET  /api/critical - 5 req/min (skip for admin)")
    print("  POST /api/login    - 5/min, 20/hour, 50/day")
    print("  GET  /api/internal - 1000 req/min (skip for local)")
    print("\nRun: curl -i http://localhost:8000/api/public\n")
    
    app.run(host="0.0.0.0", port=8000)
```

---

---

# Кэширование в AltAPI

**Кэширование** в AltAPI работает через централизованный менеджер и доступно из коробки без дополнительной настройки.

## Содержание

- [Быстрый старт](#быстрый-старт-1)
- [Декоратор @cache](#декоратор-cache)
- [Как это работает](#как-это-работает-1)
- [Полный пример](#полный-пример-1)

---

## Быстрый старт

Кэширование в AltAPI максимально просто в использовании. Всё, что нужно — импортировать декоратор:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache

app = AltAPI()


@app.get("/api/data")
@cache(expires=60)  # 60 секунд
async def get_data(request):
    return JSONResponse({"data": "cached"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

### Ключевые особенности

- ✅ **Простой импорт** — просто `from altapi.caching import cache`
- ✅ **Никакой настройки** — не нужно указывать `cache_backend`, просто `app = AltAPI()`
- ✅ **Shared mode всегда включен** — кеширование работает через центральный менеджер
- ✅ **Multi-worker поддержка** — все данные хранятся в центральном процессе
- ✅ **Менеджер запускается автоматически** при `app.run()`
- ✅ **Готово к продакшену** — работает из коробки

---

## Декоратор @cache

Основной декоратор для кэширования результатов функций.

### Синтаксис

```python
from altapi.caching import cache


@app.get("/api/endpoint")
@cache(
    expires=300,      # Время жизни кеша в секундах
    key_prefix="",    # Префикс для ключа кеша
)
async def my_endpoint(request):
    ...
```

### Параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `expires` | `int` | `300` | Время жизни кеша в секундах |
| `key_prefix` | `str` | `""` | Префикс для ключа кеша (опционально) |

### Примеры

#### Базовое использование

```python
@app.get("/api/users/{id:int}")
@cache(expires=300)  # 5 минут
async def get_user(request):
    user_id = request.path_params["id"]
    # Дорогая операция (БД, внешний API)
    return JSONResponse({"id": user_id, "name": "John"})
```

#### Разное время кеширования

```python
# Быстрые данные - 1 минута
@app.get("/api/fast")
@cache(expires=60)
async def fast_data(request):
    return JSONResponse({"data": "fast"})

# Медленные данные - 1 час
@app.get("/api/slow")
@cache(expires=3600)
async def slow_data(request):
    return JSONResponse({"data": "slow"})
```

#### Кеширование с префиксом

```python
@app.get("/api/products")
@cache(expires=600, key_prefix="products:")
async def get_products(request):
    return JSONResponse({"products": [...]})
```

---

## Как это работает

### Архитектура

AltAPI использует **централизованный менеджер** для хранения данных кеша. Это обеспечивает работу в multi-worker режиме без дополнительной настройки.

```
┌─────────────────────────────────────────────────────────┐
│                  Shared Manager Process                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Cache Store                        │    │
│  │              (in-memory)                        │    │
│  └─────────────────────────────────────────────────┘    │
│                    TCP: 127.0.0.1:58000                 │
└─────────────────────────────────────────────────────────┘
           ▲                    ▲                    ▲
           │                    │                    │
    ┌──────┴──────┐      ┌──────┴──────┐      ┌──────┴──────┐
    │  Worker 1   │      │  Worker 2   │      │  Worker 3   │
    │  (uvicorn)  │      │  (uvicorn)  │      │  (uvicorn)  │
    └─────────────┘      └─────────────┘      └─────────────┘
```

### Автоматический запуск

Менеджер запускается **автоматически** при вызове `app.run()`:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    # Менеджер запущен автоматически!
```

При остановке приложения менеджер также останавливается корректно.

### Преимущества

- **Никакой настройки** — работает из коробки
- **InMemoryCache больше не используется напрямую** — всё через `SharedCacheBackend`
- **Multi-worker поддержка** — все воркеры видят общее состояние
- **Автоматическое переподключение** — при разрыве соединения
- **Централизованное хранение** — данные в одном процессе

---

## Полный пример

```python
"""
Полный пример использования кэширования в AltAPI.
"""

import asyncio
import time

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache

# Простая инициализация - кеширование работает из коробки
app = AltAPI()


@app.get("/")
async def home(request):
    """Главная страница."""
    return JSONResponse({
        "message": "Welcome to AltAPI Caching Example",
        "endpoints": [
            "/api/expensive - Дорогая операция (кешируется 5 минут)",
            "/api/data - Данные с разным временем кеширования",
            "/api/users/{id} - Пользователи (кешируется 10 минут)",
        ]
    })


@app.get("/api/expensive")
@cache(expires=300)  # Кеш на 5 минут
async def expensive_operation(request):
    """Дорогая операция, результат кешируется."""
    await asyncio.sleep(2)  # Имитация долгой операции
    return JSONResponse({
        "message": "Expensive operation completed",
        "timestamp": time.time(),
        "note": "Первый вызов занимает 2 секунды, последующие - мгновенно (из кеша)"
    })


@app.get("/api/data")
@cache(expires=60)  # Кеш на 1 минуту
async def get_data(request):
    """Данные, которые обновляются раз в минуту."""
    return JSONResponse({
        "data": [1, 2, 3, 4, 5],
        "cached_at": time.time(),
    })


@app.get("/api/users/{id:int}")
@cache(expires=600)  # Кеш на 10 минут
async def get_user(request):
    """Пользователь по ID."""
    user_id = request.path_params["id"]
    # Имитация запроса к БД
    await asyncio.sleep(0.5)
    return JSONResponse({
        "id": user_id,
        "name": f"User {user_id}",
        "cached": True
    })


@app.get("/api/slow")
@cache(expires=3600)  # Кеш на 1 час
async def slow_data(request):
    """Медленные данные, кешируются надолго."""
    await asyncio.sleep(3)
    return JSONResponse({
        "data": "slow but cached for 1 hour",
        "timestamp": time.time(),
    })


if __name__ == "__main__":
    print("AltAPI с кешированием:")
    print("  GET /api/expensive - 2 сек первый раз, потом из кеша")
    print("  GET /api/data      - Данные с 1 минутой кеширования")
    print("  GET /api/users/1   - Пользователь с 10 минутами кеширования")
    print("  GET /api/slow      - 3 сек первый раз, кеш на 1 час")
    print("\nRun: curl http://localhost:8000/api/expensive\n")

    app.run(host="0.0.0.0", port=8000)
```

---

## См. также

- [Rate Limiting](#rate-limiting-in-altapi) — для ограничения частоты запросов
- [Middleware](DOCS.md#middleware) — для создания кастомных middleware
- [WebSocket](DOCS.md#websocket) — для WebSocket поддержки
