# Poker8 — чек-лист прод-запуска

Что нужно поднять на сервере (`45.9.150.209`), чтобы Poker8 Online заработал
как Telegram Mini App. Доступы — в `prod.md`.

Боевой домен — **`donbass.win`** (Caddy + авто-TLS, стек развёрнут в
`/opt/poker8`). `donbas.win` — то же приложение под написанием без второй "s",
обслуживается тем же site-блоком. Старый хост `64.188.67.9` с доменом
`bubbledouble.cc` остановлен.

## 1. Предусловия на сервере

- [ ] Docker + docker compose установлены (`docker --version`, `docker compose version`).
- [ ] Каталог проекта `/opt/poker8` (код через `git clone`/`rsync`).
- [ ] Порт `:8000` свободен (autorek его не занимает), порты `80/443` свободны для прокси.
- [ ] DNS: A-записи `donbass.win`, `www.donbass.win`, `donbas.win`,
      `www.donbas.win` указывают на `45.9.150.209` (Cloudflare, серое облако).

## 2. Секреты и конфиг

- [ ] Создан `/opt/poker8/.env` (в `.gitignore`, на диск сервера — вручную):
      ```
      POKER8_ENV=production
      POKER8_DATABASE_URL=postgresql+psycopg://poker8:<STRONG_PASS>@postgres:5432/poker8
      POKER8_DEFAULT_BOT_TOKEN=<TELEGRAM_BOT_TOKEN>
      POKER8_TENANTS_JSON=[{"slug":"poker8","hosts":["donbass.win","www.donbass.win","donbas.win","www.donbas.win"],"name":"Poker8","token_env":"POKER8_DEFAULT_BOT_TOKEN"}]
      POSTGRES_PASSWORD=<STRONG_PASS>
      POKER8_COORDINATOR_ENABLED=1
      POKER8_OPEN_ACCESS=0
      ```
- [ ] `hosts` в `POKER8_TENANTS_JSON` перечисляет ВСЕ имена за прокси (иначе
      `/api/auth` вернёт `404 Unknown tenant host` на том, которого нет в списке).
- [ ] Telegram-бот создан у @BotFather, токен — **отдельный** от autorek.
- [ ] `POKER8_DEFAULT_BOT_TOKEN` принадлежит **тому самому боту**, из которого
      открывается Mini App. Telegram подписывает `initData` токеном этого бота,
      поэтому чужой токен даёт `401` на каждом входе и ноль пользователей в БД —
      снаружи это выглядит как «профиль не загрузился», а не как ошибка конфига.
      Проверка: `curl -s "https://api.telegram.org/bot$TOKEN/getMe"` — `username`
      должен совпадать с ботом из BotFather (03.09.2026 здесь лежал `@pokerWbot`
      вместо `@DonbassWinBot`).

## 3. Запуск стека

- [ ] `docker compose -f compose.server.yaml up -d --build`
- [ ] Миграции применились автоматически (`alembic upgrade head` в старте контейнера).
- [ ] `curl -fsS http://127.0.0.1:8000/health/live` → `{"status":"live"}`
- [ ] `curl -fsS http://127.0.0.1:8000/health/ready` → `{"status":"ready"}`

## 4. Reverse-proxy + TLS (обязательно для Mini App)

Telegram Mini App работает только по HTTPS. Нужен nginx (или Caddy) перед `:8000`
с проксированием WebSocket для `/ws/`.

### nginx (`/etc/nginx/sites-available/poker8.conf`)

```nginx
server {
    listen 80;
    server_name donbass.win www.donbass.win donbas.win www.donbas.win;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name donbass.win www.donbass.win donbas.win www.donbas.win;

    ssl_certificate     /etc/letsencrypt/live/donbass.win/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/donbass.win/privkey.pem;

    # WebSocket: /ws/tables/{id}
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;   # долгоживущие соединения стола
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [ ] `ln -s .../sites-available/poker8.conf /etc/nginx/sites-enabled/ && nginx -t && systemctl reload nginx`
- [ ] TLS-сертификат: `certbot --nginx -d donbass.win -d www.donbass.win -d donbas.win -d www.donbas.win` (или webroot).
- [ ] Автопродление certbot включено (`systemctl status certbot.timer`).
- [ ] `Host`-заголовок доходит до приложения (нужно для маппинга tenant→host).
- [ ] Сессия-cookie `poker8_session` в проде идёт с флагом `secure` — работает
      только под HTTPS (учтено в коде).

## 5. Привязка к Telegram

- [ ] У @BotFather для бота задан Mini App / Menu Button с URL `https://donbass.win/`.
- [ ] Проверен вход через Telegram `initData` (не guest): открыть Mini App из бота.
- [ ] `POKER8_OPEN_ACCESS=0` подтверждён (гостевой вход в проде отключён).

## 6. Бэкапы и наблюдаемость

- [ ] Настроен регулярный `pg_dump` тома `poker8_pgdata` (cron + выгрузка с сервера).
- [ ] Проверены логи: `docker compose -f compose.server.yaml logs -f app`.
- [ ] `/health/ready` заведён во внешний аптайм-мониторинг.
- [ ] Просмотрена таблица `integrity_events` на аномалии перед открытием трафика.

## 7. Release gate (прогнать до выката)

```
python -m pytest -q
python -m pytest -m postgres -q
python -m pytest tests/e2e -m e2e -q
node --check static/app.js
# нагрузочный тест: 100 соединений / 20 столов (см. docs/runbooks/online-mvp.md)
```

## Открытые вопросы / решения по инфраструктуре

- ~~Домен~~ — решено: `donbass.win` (+ `donbas.win` как второе написание).
- ~~Прокси~~ — решено: Caddy с авто-TLS (`deploy/compose.caddy.yaml`), развёрнут.
  Секция nginx выше оставлена как запасной вариант.
- Размещение БД: Postgres в Compose (как сейчас) или вынести на управляемый инстанс.
- Ротация бэкапов и хранение вне сервера (S3/rsync на другой хост).
