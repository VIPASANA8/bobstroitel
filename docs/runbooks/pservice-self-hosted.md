# Свой экземпляр pservice на покер-хосте

Решение владельца (04.09): не зависеть от хоста CASE8. Платёжный сервис
`pservice` (из репозитория `VIPASANA8/case8`, `pservice-master/`) развёрнут
прямо на боевом хосте Poker8 (`45.9.150.209`). Покер ходит к нему по внутренней
docker-сети, ровно как CASE8 делает у себя — plaintext http на приватном мосту,
TLS там не нужен.

## Что где лежит

- `/opt/pservice/` на хосте — исходники pservice + `compose.poker.yml` + `.env`.
  Копия `pservice-master` из `case8` (не публичный git; обновление — новым
  tar'ом, у хоста нет доступа к тому репозиторию).
- `compose.poker.yml` — только `p2p-db` (своя postgres) + `p2p-service`, **без
  nginx** (80/443 занимает Caddy) и **без публичных портов**. Сервис на двух
  сетях: `p2p_net` (со своей БД) и внешней `poker8link`.
- `poker8link` — внешняя docker-сеть, через неё app Poker8 достаёт pservice по
  имени `p2p-service`. `compose.pilot.yaml` подключает `app` к ней.

## Как поднять / обновить

```
cd /opt/pservice
docker compose -f compose.poker.yml up -d --build
docker compose -f compose.poker.yml exec -T p2p-service curl -fsS http://127.0.0.1:8000/api/v1/health
```

Миграции применяются `entrypoint.sh` автоматически (`alembic upgrade head`).
`restart: unless-stopped` — стек переживает перезагрузку.

## Как покер к нему подключается

`.env` пилота (в `/opt/poker8/.env`), когда включаем боевой CASH:

```
POKER8_CASH_FIAT_API_URL=http://p2p-service:8000
POKER8_CASH_FIAT_TOKEN=<SHARED_SERVICE_KEY из /opt/pservice/.env>
```

`PserviceClient` допускает `http` только для внутренних адресов (docker-имя,
loopback, RFC1918); публичному по-прежнему обязателен `https`.

## Проверено 04.09

- pservice здоров: `/api/v1/health` → 200, миграции на `009_c2c_backend_approved_at`.
- покер → pservice изнутри app-контейнера: health 200, наш `SHARED_SERVICE_KEY`
  проходит (`/admin/commission` → 200), чужой ключ → 401.
- комиссия живьём: `commission_percent 1.0`, `example_fiat_100 101` (сверху).

## Единственный оставшийся внешний блокер

`/admin/partner/business` и создание реального заказа отдают **502**: pservice
на этих путях ходит в вышестоящую трейдерскую сеть
(`PARTNER_API_URL=https://80.78.19.112:8443`), а её IP-фильтр **не пускает этот
хост**. Нужен whitelist IP `45.9.150.209` у партнёра (тот же firewall, что ждём).
До этого pservice поднимается, мигрирует и отвечает на всё локальное, но
реальный рублёвый заказ не завершится.

`PARTNER_TLS_VERIFY=false` унаследован из pservice — это его внутренняя связь с
самоподписанным партнёром на голом IP, к нашему покерному коду отношения не
имеет (наш `PserviceClient` к самому pservice ходит с `verify=True`, а внутри
docker-сети — по http).

## Пока НЕ включено (осознанно)

- `cash_mode` пилота остаётся `mock`. Боевой CASH не включаем, пока нет
  провайдера выплат и пока партнёр не пускает этот хост.
- `C2C_ENABLED=false` в pservice: у pservice свой TRON-C2C, у покера свой
  `Trc20DepositWatcher` — чьим пользуемся, отдельное решение, чтобы не
  задваивать зачисления.
