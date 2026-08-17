# Poker8 — деплой с Caddy (авто-TLS)

Вариант reverse-proxy на Caddy вместо nginx: сам получает и продлевает
Let's Encrypt сертификат и прозрачно проксирует WebSocket — ручной конфиг TLS
не нужен.

## Предпосылки
- DNS: A-запись домена из `Caddyfile` указывает на сервер (`64.188.67.9`).
- Порты 80 и 443 свободны.
- `/root/poker8/.env` заполнен (см. `.env.production.example`).

## Запуск
```
cd /root/poker8
# домен в deploy/Caddyfile заменить на реальный
docker compose -f compose.server.yaml -f deploy/compose.caddy.yaml up -d --build
docker compose -f compose.server.yaml -f deploy/compose.caddy.yaml logs -f caddy
```

Caddy при первом старте сам выпустит сертификат (нужен доступный 80/443 порт и
корректный DNS). После этого:
```
curl -fsS https://bubbledouble.cc/health/ready
```

## Заметки
- В этом варианте `app` больше не публикует `:8000` наружу (оверрайд сбрасывает
  `ports`) — вход только через Caddy по 443.
- Для отладки изнутри сервера healthcheck app по-прежнему бьёт в `127.0.0.1:8000`
  внутри контейнера.
- nginx-вариант (если предпочтёте его) — в `docs/runbooks/prod-launch-checklist.md`.
