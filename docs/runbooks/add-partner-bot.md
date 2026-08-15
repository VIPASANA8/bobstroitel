# Подключение второго Telegram-бота

1. Создайте второго бота в BotFather и задайте Mini App URL на тот же online deployment.
2. Добавьте tenant в `POKER8_TENANTS_JSON` с уникальным `slug`, exact `hosts`, display name, `token_env` и branding variables.
3. Определите секрет `token_env` в окружении процесса; токен не добавляется в git и не возвращается через `/api/config`.
4. Перезапустите приложение, выполните `alembic upgrade head`, затем проверьте `/health/ready` и Telegram initData login с новым Host.
5. Выполните two-tenant smoke test: один Telegram ID должен получить тот же internal user ID, wallet и acquisition tenant первого партнёра.
6. Для rotation задайте новый секрет, перезапустите deployment и отзовите старые sessions. Для disable установите tenant status inactive и проверьте, что login отклоняется.

Игровой пул, столы и virtual PLAY общий network-контур; tenant меняет branding/auth gateway, но не создаёт отдельный баланс.
