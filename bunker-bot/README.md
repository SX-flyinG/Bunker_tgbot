# ☢ BUNKER BOT — Полная инструкция по запуску

## Структура проекта

```
bunker-bot/
├── bot/
│   ├── main.py          # Точка входа бота
│   ├── config.py        # Токен и URL настройки
│   ├── handlers.py      # Все команды и колбэки
│   ├── storage.py       # Хранилище состояний игры
│   ├── cards.py         # Все карты (100+ каждого типа)
│   └── requirements.txt
└── webapp/
    └── index.html       # Mini App (один файл)
```

---

## Шаг 1: Создай бота

1. Напиши @BotFather в Telegram
2. `/newbot` → задай имя и юзернейм
3. Скопируй **токен** — вставь в `bot/config.py`
4. `/setmenubutton` → выбери бота → Menu Button URL → вставь URL твоего Mini App
5. `/setdomain` → укажи домен твоего хостинга

---

## Шаг 2: Задеплой Mini App (бесплатно)

### Вариант A: GitHub Pages (самый простой)

1. Создай репозиторий на GitHub (публичный)
2. Загрузи `webapp/index.html`
3. Settings → Pages → Source: `main` / `root`
4. Твой URL: `https://USERNAME.github.io/REPO_NAME`
5. Вставь в `config.py`: `WEBAPP_URL = "https://USERNAME.github.io/REPO_NAME"`

### Вариант B: Vercel

1. Зайди на vercel.com
2. Import → выбери репо с папкой `webapp/`
3. Получи URL вида `your-app.vercel.app`

### Вариант C: ngrok (для локальной разработки)

```bash
ngrok http 5500
# Скопируй https URL в WEBAPP_URL
```

---

## Шаг 3: Установка и запуск бота

```bash
cd bot/
pip install -r requirements.txt

# Задай переменные окружения:
export BOT_TOKEN="1234567890:ABCdefGHI..."
export WEBAPP_URL="https://your-app.vercel.app"

python main.py
```

---

## Как играть

### Команды в Telegram:

| Команда | Действие |
|---------|----------|
| `/create` | Создать комнату (выбрать 8-12 игроков) |
| `/join КОД` | Войти в комнату по коду |
| `/room` | Статус комнаты |
| `/card` | Посмотреть свою карточку |
| `/players` | Все игроки и их открытые карты |
| `/next` | Следующий раунд (только хост) |
| `/vote` | Проголосовать за исключение |
| `/leave` | Покинуть комнату |

### Правила раскрытия карт:

- **Раунд 1**: каждый может открыть **только профессию**
- **Раунд 2+**: можно открыть **любую одну карту** за раунд
- **Раунд 3**: автоматически раскрывается **особая функция бункера**
- **При исключении**: все карты игрока **раскрываются публично**

### Голосование:

Начинается с раунда 2. Каждый голосует командой `/vote` или через Mini App.
Кто набрал больше голосов — исключается. При ничье — повторное голосование.

---

## Расширение до продакшена

Для реального многопользовательского состояния замени `storage.py` на:

```python
# Redis через aioredis
import aioredis
redis = aioredis.from_url("redis://localhost")
await redis.set(f"room:{code}", json.dumps(room_data))
```

Или используй PostgreSQL через SQLAlchemy async.

---

## Технологии

- **Bot**: Python 3.11+, aiogram 3.x
- **Mini App**: Vanilla HTML/CSS/JS, Telegram Web App SDK
- **Storage**: In-memory dict (для продакшена → Redis)
- **Hosting**: GitHub Pages / Vercel / Railway
