# Poker8 — деплой с Caddy (авто-TLS)

Вариант reverse-proxy на Caddy вместо nginx: сам получает и продлевает
Let's Encrypt сертификат и прозрачно проксирует WebSocket — ручной конфиг TLS
не нужен.

## Предпосылки
- DNS: A-записи всех имён из `Caddyfile` указывают на сервер (`45.9.150.209`),
  через Cloudflare без проксирования (серое облако) — иначе Caddy не пройдёт
  ACME-проверку Let's Encrypt.
- Порты 80 и 443 свободны.
- `/opt/poker8/.env` заполнен (см. `.env.production.example`).

## Запуск
```
cd /opt/poker8
# домены в deploy/Caddyfile — donbass.win и вариант написания donbas.win
docker compose -f compose.server.yaml -f deploy/compose.caddy.yaml up -d --build
docker compose -f compose.server.yaml -f deploy/compose.caddy.yaml logs -f caddy
```

Caddy при первом старте сам выпустит сертификат (нужен доступный 80/443 порт и
корректный DNS). После этого:
```
curl -fsS https://donbass.win/health/ready
```

## Заметки
- В этом варианте `app` больше не публикует `:8000` наружу (оверрайд сбрасывает
  `ports`) — вход только через Caddy по 443.
- Для отладки изнутри сервера healthcheck app по-прежнему бьёт в `127.0.0.1:8000`
  внутри контейнера.
- nginx-вариант (если предпочтёте его) — в `docs/runbooks/prod-launch-checklist.md`.
